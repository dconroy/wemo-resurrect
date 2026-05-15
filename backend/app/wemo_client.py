"""Local WeMo discovery and control via pywemo, with a minimal SOAP fallback."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pywemo
import requests
from pywemo.ouimeaux_device import Device
from tenacity import retry, stop_after_attempt, wait_exponential

LOG = logging.getLogger(__name__)

PROBE_PORTS = (49153, 49152, 49154, 49151, 49155, 49156, 49157, 49158, 49159)
REQUEST_TIMEOUT = 8.0


@dataclass
class DeviceSnapshot:
    name: str
    ip: str
    port: int | None
    model: str | None
    serial: str | None
    udn: str
    binary_state: int | None


def _device_to_snapshot(dev: Device, state: int | None) -> DeviceSnapshot:
    return DeviceSnapshot(
        name=dev.name,
        ip=dev.host,
        port=int(dev.port) if dev.port else None,
        model=dev.model_name or dev.model or None,
        serial=dev.serial_number or None,
        udn=dev.udn,
        binary_state=state,
    )


class WemoClientError(Exception):
    pass


def discover_wemos(
    *, debug: bool = False, ssdp_timeout: float | None = None
) -> list[DeviceSnapshot]:
    """SSDP / UPnP discovery for LAN WeMo devices."""
    scan_kw: dict = {}
    if ssdp_timeout is not None:
        scan_kw["timeout"] = ssdp_timeout
    try:
        devices = pywemo.discover_devices(debug=debug, **scan_kw)
    except Exception as exc:  # pragma: no cover - network
        LOG.warning("pywemo discovery failed: %s", exc)
        raise WemoClientError(f"Discovery failed: {exc}") from exc
    out: list[DeviceSnapshot] = []
    for dev in devices:
        try:
            state = int(dev.get_state(force_update=True))
        except Exception as exc:
            LOG.debug("Could not read state for %s: %s", dev.host, exc)
            state = None
        out.append(_device_to_snapshot(dev, state))
    return out


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4, min=0.5, max=4))
def _connect_device(ip: str) -> Device:
    url = pywemo.setup_url_for_address(ip)
    return pywemo.discovery.device_from_description(url)


def _set_state_pywemo(dev: Device, on: bool) -> None:
    if hasattr(dev, "set_state"):
        dev.set_state(1 if on else 0)
        return
    if on and hasattr(dev, "on"):
        dev.on()
        return
    if not on and hasattr(dev, "off"):
        dev.off()
        return
    raise WemoClientError("Device does not expose switch control via pywemo")


def get_device_snapshot(ip: str) -> DeviceSnapshot:
    """Connect by IP and return metadata + binary state."""
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            dev = _connect_device(ip)
            state = int(dev.get_state(force_update=True))
            return _device_to_snapshot(dev, state)
        except Exception as exc:
            last_err = exc
            LOG.debug("pywemo snapshot attempt %s for %s failed: %s", attempt + 1, ip, exc)
    assert last_err is not None
    soap_snap = _soap_try_snapshot(ip)
    if soap_snap:
        return soap_snap
    raise WemoClientError(f"Could not reach WeMo at {ip}: {last_err}") from last_err


def set_device_power(ip: str, on: bool) -> DeviceSnapshot:
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            dev = _connect_device(ip)
            _set_state_pywemo(dev, on)
            state = int(dev.get_state(force_update=True))
            return _device_to_snapshot(dev, state)
        except Exception as exc:
            last_err = exc
            LOG.debug("pywemo set_state attempt %s for %s failed: %s", attempt + 1, ip, exc)
    if _soap_set_binary_state(ip, 1 if on else 0):
        st = _soap_get_binary_state(ip)
        return DeviceSnapshot(
            name=f"WeMo ({ip})",
            ip=ip,
            port=_probe_port(ip),
            model=None,
            serial=None,
            udn=f"soap-fallback:{ip}",
            binary_state=st,
        )
    assert last_err is not None
    raise WemoClientError(f"Could not control WeMo at {ip}: {last_err}") from last_err


# --- Minimal SOAP fallback (BasicEvent) ---


_NS = {"s": "http://schemas.xmlsoap.org/soap/envelope/"}


def _probe_port(host: str) -> int | None:
    for port in PROBE_PORTS:
        try:
            r = requests.get(
                f"http://{host}:{port}/setup.xml",
                timeout=REQUEST_TIMEOUT,
            )
            if r.ok and b"Belkin" in r.content:
                return port
        except requests.RequestException:
            continue
    return None


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _parse_basicevent_control_url(setup_xml: bytes, host: str, port: int) -> str | None:
    try:
        root = ET.fromstring(setup_xml)
    except ET.ParseError:
        return None
    for service in root.iter():
        if _local_tag(service.tag) != "service":
            continue
        st: str | None = None
        cu: str | None = None
        for child in service:
            ln = _local_tag(child.tag)
            if ln == "serviceType" and child.text:
                st = child.text.strip()
            if ln == "controlURL" and child.text:
                cu = child.text.strip()
        if st and "basicevent" in st.lower() and cu:
            if cu.startswith("http"):
                return cu
            return f"http://{host}:{port}{cu}"
    return None


def _soap_post(control_url: str, action: str, body_inner: str) -> requests.Response:
    soap_action = f'"urn:Belkin:service:basicevent:1#{action}"'
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
{body_inner}
</s:Body>
</s:Envelope>"""
    return requests.post(
        control_url,
        data=envelope.encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": soap_action,
        },
        timeout=REQUEST_TIMEOUT,
    )


def _soap_get_binary_state(host: str) -> int | None:
    port = _probe_port(host)
    if port is None:
        return None
    try:
        r = requests.get(f"http://{host}:{port}/setup.xml", timeout=REQUEST_TIMEOUT)
        cu = _parse_basicevent_control_url(r.content, host, port)
        if not cu:
            return None
        inner = '<u:GetBinaryState xmlns:u="urn:Belkin:service:basicevent:1"></u:GetBinaryState>'
        resp = _soap_post(cu, "GetBinaryState", inner)
        if not resp.ok:
            return None
        m = re.search(r"<BinaryState[^>]*>([01])</BinaryState>", resp.text)
        if m:
            return int(m.group(1))
    except requests.RequestException as exc:
        LOG.debug("SOAP GetBinaryState failed for %s: %s", host, exc)
    return None


def _soap_set_binary_state(host: str, state: int) -> bool:
    port = _probe_port(host)
    if port is None:
        return False
    try:
        r = requests.get(f"http://{host}:{port}/setup.xml", timeout=REQUEST_TIMEOUT)
        cu = _parse_basicevent_control_url(r.content, host, port)
        if not cu:
            return False
        inner = f"""<u:SetBinaryState xmlns:u="urn:Belkin:service:basicevent:1">
<BinaryState>{state}</BinaryState>
</u:SetBinaryState>"""
        resp = _soap_post(cu, "SetBinaryState", inner)
        return resp.ok
    except requests.RequestException as exc:
        LOG.debug("SOAP SetBinaryState failed for %s: %s", host, exc)
        return False


def _soap_try_snapshot(ip: str) -> DeviceSnapshot | None:
    st = _soap_get_binary_state(ip)
    if st is None:
        return None
    port = _probe_port(ip)
    return DeviceSnapshot(
        name=f"WeMo ({ip})",
        ip=ip,
        port=port,
        model="SOAP fallback",
        serial=None,
        udn=f"soap-fallback:{ip}",
        binary_state=st,
    )
