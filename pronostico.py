"""Cumbres Digitales - pronóstico diario en el punto más alto de cada ruta.

Pide a Open-Meteo (gratuito, sin clave) el pronóstico de hoy y mañana a la
altura exacta del punto más alto de cada ruta y dibuja una imagen por ruta:
  site/img/NNN.png   (dirección fija: el sitio la muestra y se actualiza sola)
Datos: Open-Meteo.com (CC BY 4.0). Corre todos los días en GitHub Actions.
"""
import json, os, sys, urllib.request, urllib.parse, datetime
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, 'site', 'img')
TZ = 'America/Argentina/Mendoza'
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

# Códigos de tiempo de la OMM que usa Open-Meteo
WMO = {0: 'Despejado', 1: 'Mayormente despejado', 2: 'Parcialmente nublado', 3: 'Nublado',
       45: 'Niebla', 48: 'Niebla con escarcha', 51: 'Llovizna débil', 53: 'Llovizna', 55: 'Llovizna intensa',
       56: 'Llovizna helada', 57: 'Llovizna helada', 61: 'Lluvia débil', 63: 'Lluvia', 65: 'Lluvia intensa',
       66: 'Lluvia helada', 67: 'Lluvia helada', 71: 'Nevada débil', 73: 'Nevada', 75: 'Nevada intensa',
       77: 'Granizo fino', 80: 'Chaparrones', 81: 'Chaparrones', 82: 'Chaparrones fuertes',
       85: 'Chaparrones de nieve', 86: 'Chaparrones de nieve', 95: 'Tormenta eléctrica',
       96: 'Tormenta con granizo', 99: 'Tormenta con granizo'}


def fuente(tam, negrita=False):
    for f in (['DejaVuSans-Bold.ttf', 'arialbd.ttf'] if negrita else ['DejaVuSans.ttf', 'arial.ttf']):
        for d in ('/usr/share/fonts/truetype/dejavu/', ''):
            try:
                return ImageFont.truetype(d + f, tam)
            except OSError:
                pass
    return ImageFont.load_default()


def pedir(rutas):
    q = {'latitude': ','.join(str(r['lat']) for r in rutas),
         'longitude': ','.join(str(r['lon']) for r in rutas),
         'elevation': ','.join(str(r['alt']) for r in rutas),
         'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,'
                  'precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max',
         'hourly': 'freezing_level_height',
         'timezone': TZ, 'forecast_days': 2, 'wind_speed_unit': 'kmh'}
    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'cumbres-digitales-pronostico'}), timeout=120))
    return r if isinstance(r, list) else [r]


def color_t(t):
    if t <= -10: return (120, 160, 255)
    if t <= 0: return (140, 200, 255)
    if t <= 15: return (150, 220, 170)
    if t <= 25: return (240, 200, 90)
    return (245, 140, 70)


def dibujar(ruta, d, ahora):
    D = d['daily']; H = d['hourly']
    W, Hh = 760, 250
    im = Image.new('RGB', (W, Hh), (30, 30, 30)); g = ImageDraw.Draw(im)
    F, FB, FS, FT = fuente(15), fuente(17, True), fuente(12), fuente(26, True)
    lugar = 'la cumbre' if ruta['tipo'] == 'Cumbre' else 'el punto más alto'
    g.text((14, 10), f"Pronóstico en {lugar} · {ruta['alt']} msnm", font=FB, fill=(240, 240, 240))
    for k in range(2):
        x0 = 14 + k * 373
        fecha = datetime.date.fromisoformat(D['time'][k])
        g.rounded_rectangle((x0, 40, x0 + 360, 200), radius=10, fill=(42, 42, 42))
        g.text((x0 + 12, 48), f"{'Hoy' if k == 0 else 'Mañana'} · {DIAS[fecha.weekday()]} {fecha:%d/%m}", font=FB, fill=(90, 170, 255))
        g.text((x0 + 12, 72), WMO.get(D['weather_code'][k], ''), font=F, fill=(220, 220, 220))
        tx, tn = D['temperature_2m_max'][k], D['temperature_2m_min'][k]
        g.text((x0 + 12, 96), f"{round(tx)}°", font=FT, fill=color_t(tx))
        g.text((x0 + 70, 106), 'máx', font=FS, fill=(170, 170, 170))
        g.text((x0 + 112, 96), f"{round(tn)}°", font=FT, fill=color_t(tn))
        g.text((x0 + 170, 106), 'mín', font=FS, fill=(170, 170, 170))
        raf = D['wind_gusts_10m_max'][k]
        g.text((x0 + 12, 136), f"Ráfagas de viento hasta {round(raf)} km/h" + (' · fuerte' if raf >= 60 else ''), font=F,
               fill=(255, 110, 110) if raf >= 60 else (220, 220, 220))
        pr, nv, pp = D['precipitation_sum'][k] or 0, D['snowfall_sum'][k] or 0, D['precipitation_probability_max'][k]
        txt = f"Nieve {nv:.0f} cm" if nv >= 0.5 else (f"Lluvia {pr:.0f} mm" if pr >= 0.5 else 'Sin precipitación')
        if pp is not None: txt += f" · prob. {pp}%"
        g.text((x0 + 12, 156), txt, font=F, fill=(220, 220, 220))
        fl = [v for t, v in zip(H['time'], H['freezing_level_height']) if t.startswith(D['time'][k]) and v is not None]
        if fl:
            g.text((x0 + 12, 176), f"Isoterma 0 °C entre {round(min(fl), -2):.0f} y {round(max(fl), -2):.0f} m", font=F, fill=(180, 210, 255))
    g.text((14, 210), f"Actualizado {ahora:%d/%m %H:%M} (hora de Mendoza) · modelo de pronóstico Open-Meteo, a {ruta['alt']} m de altura.", font=FS, fill=(170, 170, 170))
    g.text((14, 228), 'Orientativo: confirmalo en Windy u otro pronóstico de montaña antes de salir. Cumbres Digitales', font=FS, fill=(170, 170, 170))
    return im


def main():
    rutas = json.load(open(os.path.join(AQUI, 'data', 'rutas.json'), encoding='utf-8'))
    if len(sys.argv) > 1:
        rutas = [r for r in rutas if r['n'] in {int(a) for a in sys.argv[1:]}]
    os.makedirs(SALIDA, exist_ok=True)
    ahora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    ok = 0
    for i in range(0, len(rutas), 40):
        lote = rutas[i:i + 40]
        for ruta, d in zip(lote, pedir(lote)):
            dibujar(ruta, d, ahora).save(os.path.join(SALIDA, f"{ruta['n']:03d}.png"), optimize=True)
            ok += 1
    open(os.path.join(AQUI, 'site', 'index.html'), 'w', encoding='utf-8').write(
        '<!doctype html><meta charset="utf-8"><title>Pronósticos Cumbres Digitales</title>'
        f'<p>Imágenes de pronóstico por ruta, actualizadas {ahora:%d/%m/%Y %H:%M}. '
        'Datos: <a href="https://open-meteo.com/">Open-Meteo.com</a> (CC BY 4.0). '
        '<a href="https://cumbresdigitales.wordpress.com/">Cumbres Digitales</a></p>')
    print(f'{ok} imágenes generadas')


if __name__ == '__main__':
    main()
