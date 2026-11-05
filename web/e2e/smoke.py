"""Prueba el flujo principal con la API y el frontend activos: python web/e2e/smoke.py

Requiere Playwright para Python. No depende de cuántas vallas haya, salvo que exista alguna en la zona.
"""
import re

from playwright.sync_api import expect, sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

    page.goto("http://localhost:5173/")
    expect(page.locator(".summary")).to_contain_text(re.compile(r"^[1-9]\d* vallas"))
    expect(page.locator(".cluster").first).to_be_visible()

    # Un filtro sin coincidencias vacía la lista y lo explica
    page.get_by_label("Buscar").fill("zzzz")
    expect(page.get_by_text("No encontramos vallas en el mapa")).to_be_visible()
    page.get_by_role("button", name="Quitar filtros").click()

    # La búsqueda ignora tildes y encuentra vallas fuera de la vista actual
    page.get_by_label("Buscar").fill("duran")
    expect(page.locator(".summary")).to_contain_text(re.compile(r"[1-9]\d* vallas encontradas"))
    page.get_by_role("button", name="Quitar filtros").click()

    # Solo exactas: todas las filas deben tener el pin de ubicación exacta
    page.get_by_text("Más filtros").click()
    page.get_by_label("Solo con ubicación exacta").check()
    expect(page.locator(".results .pin--approximate")).to_have_count(0)
    expect(page.locator(".results button").first).to_be_visible()

    # La ficha muestra ubicación y una forma de llegar
    page.locator(".results button").first.click()
    expect(page.locator(".card")).to_contain_text("Ubicación exacta")
    expect(page.get_by_role("link", name="Cómo llegar")).to_have_attribute("href", re.compile(r"destination=-?\d"))

    # Los anuncios de ejemplo caben en la valla
    next_example = page.get_by_role("button", name="Ver el siguiente ejemplo")
    for _ in range(3):
        overflow = page.locator(".sign .ad text").evaluate_all(
            "texts => texts.filter(t => { const b = t.getBBox(); return b.x < 0 || b.x + b.width > 250 }).length"
        )
        assert overflow == 0, "texto de ejemplo cortado"
        next_example.click()

    # Para reportar solo hace falta marcar el punto. No envía nada.
    page.get_by_role("button", name="Volver a la lista").click()
    page.get_by_role("button", name="Viste una valla").click()
    expect(page.get_by_role("button", name="Enviar reporte")).to_be_disabled()
    page.locator(".map").click(position={"x": 400, "y": 400})
    expect(page.get_by_role("button", name="Enviar reporte")).to_be_enabled()

    assert not errors, errors
    browser.close()
    print("ok")
