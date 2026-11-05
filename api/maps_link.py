"""Saca las coordenadas de un enlace de Google Maps, incluidos los cortos de "Compartir"."""
import re
import urllib.error
import urllib.parse
import urllib.request

NUMBER = r"(-?\d{1,3}\.\d+)"
# De más a menos precisa: !3d!4d es el lugar marcado; @ es solo el centro de la vista
PATTERNS = [
    rf"!3d{NUMBER}!4d{NUMBER}",
    rf"[?&](?:q|query|ll|destination|daddr|center)=(?:loc:)?{NUMBER},\s*\+?{NUMBER}",
    rf"/(?:place|search|dir)/{NUMBER},\s*\+?{NUMBER}",
    rf"@{NUMBER},{NUMBER}",
]
SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl", "g.co"}
GOOGLE_HOST = re.compile(r"(?:(?:www|maps|consent)\.)?google\.[a-z]{2,3}(?:\.[a-z]{2})?")
MAX_REDIRECTS = 5


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def is_allowed(url):
    """Solo se visitan hosts de Google por HTTPS: el enlace lo escribe cualquiera."""
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host in SHORT_HOSTS or bool(GOOGLE_HOST.fullmatch(host)))


def coords_from_text(text):
    """Busca coordenadas en un enlace ya decodificado. Devuelve (lat, lng) o None."""
    decoded = urllib.parse.unquote(text)
    for pattern in PATTERNS:
        match = re.search(pattern, decoded)
        if match:
            return float(match[1]), float(match[2])
    return None


def resolve(url):
    """Devuelve (lat, lng), o None si el enlace no trae coordenadas. ValueError si no es de Google."""
    url = url.strip().replace("http://", "https://", 1)
    opener = urllib.request.build_opener(NoRedirect)
    for _ in range(MAX_REDIRECTS + 1):
        if not is_allowed(url):
            raise ValueError("El enlace no es de Google Maps")
        coords = coords_from_text(url)
        if coords:
            return coords
        # El aviso de cookies de Google guarda el destino real en "continue"
        parts = urllib.parse.urlsplit(url)
        target = urllib.parse.parse_qs(parts.query).get("continue")
        if parts.hostname.startswith("consent.") and target:
            url = target[0]
            continue
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            # Una página sin redirección no trae el punto en la URL. Su HTML sí tiene un "center",
            # pero es el de la vista y puede estar a kilómetros: mejor no adivinar.
            opener.open(request, timeout=8).close()
            return None
        except urllib.error.HTTPError as response:
            if response.code not in (301, 302, 303, 307, 308):
                return None
            url = urllib.parse.urljoin(url, response.headers.get("Location", ""))
        except OSError:
            return None
    return None


if __name__ == "__main__":
    assert coords_from_text("https://www.google.com/maps/place/X/@-2.1,-79.8,17z/data=!3m1!4b1!3d-2.141907!4d-79.889507") == (-2.141907, -79.889507)
    assert coords_from_text("https://www.google.com/maps?q=-2.15,-79.9") == (-2.15, -79.9)
    assert coords_from_text("https://maps.google.com/?q=-2.15%2C-79.9&z=15") == (-2.15, -79.9)
    assert coords_from_text("https://www.google.com/maps/search/-2.15,+-79.9") == (-2.15, -79.9)
    assert coords_from_text("https://www.google.com/maps/@-2.15,-79.9,15z") == (-2.15, -79.9)
    assert coords_from_text("https://www.google.com/maps/place/Mall+del+Sol") is None
    assert is_allowed("https://maps.app.goo.gl/abc")
    assert is_allowed("https://www.google.com.ec/maps")
    for bad in ("http://maps.app.goo.gl/a", "https://google.com.evil.io/", "https://evil.io/?google.com", "https://169.254.169.254/"):
        assert not is_allowed(bad), bad
    print("ok")
