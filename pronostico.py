"""Cumbres Digitales - pronóstico diario en el punto más alto de cada ruta.

Pide a Open-Meteo (gratuito, sin clave) el pronóstico de hoy y mañana a la
altura exacta del punto más alto de cada ruta y dibuja una imagen por ruta:
  site/img/NNN.png   (dirección fija: el sitio la muestra y se actualiza sola)
Datos: Open-Meteo.com (CC BY 4.0). Corre todos los días en GitHub Actions.
"""
import json, os, sys, urllib.request, urllib.parse, datetime
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
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
         'timezone': TZ, 'forecast_days': 16, 'wind_speed_unit': 'kmh'}
    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)
    from perfil_clima import _pedir
    return _pedir(url)


def color_t(t):
    if t <= -10: return (120, 160, 255)
    if t <= 0: return (140, 200, 255)
    if t <= 15: return (150, 220, 170)
    if t <= 25: return (240, 200, 90)
    return (245, 140, 70)


CORTA = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']


def tenue(c, f):
    return tuple(int(30 + (v - 30) * f) for v in c)


def dibujar(ruta, d, ahora):
    D = d['daily']; H = d['hourly']
    nd = len(D['time'])
    W, RH, TOP = 600, 27, 84
    alto = TOP + nd * RH + 2 * 24 + 74
    im = Image.new('RGB', (W, alto), (30, 30, 30)); g = ImageDraw.Draw(im)
    F, FB, FS, FH = fuente(17), fuente(18, True), fuente(13), fuente(13, True)
    lugar = 'la cumbre' if ruta['tipo'] == 'Cumbre' else 'el punto más alto'
    g.text((14, 10), f"Pronóstico {nd} días en {lugar} · {ruta['alt']} msnm", font=FB, fill=(240, 240, 240))
    g.text((14, 34), f"Actualizado {ahora:%d/%m %H:%M} (hora de Mendoza)", font=FS, fill=(170, 170, 170))
    X = [14, 128, 186, 244, 340, 490]
    for x, t in zip(X, ['Día', 'Máx', 'Mín', 'Ráfagas', 'Precipitación', '0 °C desde']):
        g.text((x, 60), t, font=FH, fill=(150, 150, 150))
    y = TOP
    for k in range(nd):
        if k in (2, 7):
            txt = 'Días 3 a 7 · confiabilidad aceptable' if k == 2 else 'Días 8 a 16 · solo tendencia: puede cambiar mucho'
            g.line((14, y + 11, W - 14, y + 11), fill=(70, 70, 70))
            tw = g.textlength(txt, font=FS); g.rectangle((W / 2 - tw / 2 - 8, y + 2, W / 2 + tw / 2 + 8, y + 20), fill=(30, 30, 30))
            g.text((W / 2 - tw / 2, y + 3), txt, font=FS, fill=(200, 170, 90) if k == 2 else (200, 120, 90)); y += 24
        f = 1.0 if k < 2 else (0.85 if k < 7 else 0.6)
        if k < 2: g.rounded_rectangle((8, y, W - 8, y + RH - 2), radius=6, fill=(44, 52, 64))
        fecha = datetime.date.fromisoformat(D['time'][k])
        dia = ('Hoy ' if k == 0 else 'Mañana ' if k == 1 else '') + f"{CORTA[fecha.weekday()]} {fecha:%d}"
        g.text((X[0], y + 3), dia, font=F, fill=tenue((235, 235, 235), f))
        tx, tn = D['temperature_2m_max'][k], D['temperature_2m_min'][k]
        if tx is not None: g.text((X[1], y + 3), f"{round(tx)}°", font=F, fill=tenue(color_t(tx), f))
        if tn is not None: g.text((X[2], y + 3), f"{round(tn)}°", font=F, fill=tenue(color_t(tn), f))
        raf = D['wind_gusts_10m_max'][k]
        if raf is not None:
            g.text((X[3], y + 3), f"{round(raf)} km/h", font=F, fill=tenue((255, 110, 110) if raf >= 60 else (220, 220, 220), f))
        pr, nv = D['precipitation_sum'][k] or 0, D['snowfall_sum'][k] or 0
        tor = (D['weather_code'][k] or 0) >= 95
        txt = f"nieve {nv:.0f} cm" if nv >= 0.5 else (f"lluvia {pr:.0f} mm" if pr >= 0.5 else '—')
        if tor: txt = 'tormenta' + ('' if txt == '—' else ', ' + txt.split()[0])
        g.text((X[4], y + 3), txt, font=F, fill=tenue((150, 210, 255) if nv >= 0.5 else (255, 200, 90) if tor else (220, 220, 220), f))
        fl = [v for t, v in zip(H['time'], H['freezing_level_height']) if t.startswith(D['time'][k]) and v is not None]
        if fl: g.text((X[5], y + 3), f"{round(min(fl), -2):.0f} m", font=F, fill=tenue((180, 210, 255), f))
        y += RH
    y += 8
    for t in [f"Modelo de pronóstico Open-Meteo, calculado a {ruta['alt']} m de altura. Las ráfagas",
              'varían mucho entre modelos. Rojo: ráfagas de 60 km/h o más. "0 °C desde": altura',
              'mínima de la isoterma 0 °C en el día. Orientativo: confirmalo antes de salir.']:
        g.text((14, y), t, font=FS, fill=(165, 165, 165)); y += 18
    return im


PUBLICADO = 'https://jgogol.github.io/cumbres-pronostico/img'


def rescatar(n):
    """Si una ruta falla, conserva las imágenes de la corrida anterior (ya publicadas)."""
    nn = f'{n:03d}'; ok = 0
    nombres = [f'{nn}.png', f'{nn}.gif'] + [f'{nn}/{x}' for x in ['semana.png'] + [f'dia{k}.png' for k in range(1, 8)]]
    for nom in nombres:
        destino = os.path.join(SALIDA, nom)
        if os.path.exists(destino): continue
        try:
            b = urllib.request.urlopen(urllib.request.Request(f'{PUBLICADO}/{nom}', headers={'User-Agent': 'cumbres-digitales-pronostico'}), timeout=30).read()
            os.makedirs(os.path.dirname(destino), exist_ok=True); open(destino, 'wb').write(b); ok += 1
        except Exception:
            pass
    return f' -> se mantienen {ok} imágenes anteriores'


def guardar_historial(n, ahora, datos):
    import gzip
    carpeta = os.path.join(AQUI, 'historial', f'{n:03d}'); os.makedirs(carpeta, exist_ok=True)
    with gzip.open(os.path.join(carpeta, f'{ahora:%Y-%m-%d_%H}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, separators=(',', ':'))


def main():
    rutas = json.load(open(os.path.join(AQUI, 'data', 'rutas.json'), encoding='utf-8'))
    if len(sys.argv) > 1:
        rutas = [r for r in rutas if str(r['n']) in sys.argv[1:] or f"{r['n']:03d}" in sys.argv[1:]]
    os.makedirs(SALIDA, exist_ok=True)
    ahora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    import traceback, time
    from animado import gif
    ok, errores = 0, []
    for i in range(0, len(rutas), 20):
        lote = rutas[i:i + 20]
        try:
            datos = pedir(lote)
        except Exception:
            time.sleep(20)
            try:
                datos = pedir(lote)
            except Exception:
                errores.append(f'lote {i}: ' + traceback.format_exc()); continue
        for ruta, d in zip(lote, datos):
            try:
                dibujar(ruta, d, ahora).save(os.path.join(SALIDA, f"{ruta['n']:03d}.png"), optimize=True)
                gif(ruta, d, ahora, os.path.join(SALIDA, f"{ruta['n']:03d}.gif"))
                pf = os.path.join(AQUI, 'data', 'perfiles', f"{ruta['n']:03d}.json")
                hist = {'ruta': ruta['n'], 'alt_cumbre': ruta['alt'], 'generado': ahora.isoformat(timespec='minutes'),
                        'fuente': 'Open-Meteo forecast', 'diario_cumbre': d['daily']}
                if os.path.exists(pf):
                    from altura_hora import altura_hora
                    Dh = altura_hora(ruta, json.load(open(pf)), ahora, SALIDA)
                    hist['por_altura'] = {'alturas': Dh.alts, 'horas': Dh.horas, 'temperatura': Dh.T, 'rafagas': Dh.G,
                                          'precipitacion_max': Dh.lluvia, 'nieve_cumbre': Dh.nieve, 'codigo_tiempo': Dh.wcode}
                guardar_historial(ruta['n'], ahora, hist)
                ok += 1
                time.sleep(0.4)  # no saturar el servicio gratuito
            except Exception:
                errores.append(f"ruta {ruta['n']}: " + traceback.format_exc().strip().splitlines()[-1] + rescatar(ruta['n']))
        time.sleep(1)
    if len(sys.argv) == 1 or 'cerros' in sys.argv:
        try:
            from cerros import generar
            okc, errc = generar(ahora); errores += errc
        except Exception:
            okc = 0; errores.append('cerros: ' + traceback.format_exc().strip().splitlines()[-1])
    else:
        okc = 0
    open(os.path.join(AQUI, 'site', 'log.txt'), 'w', encoding='utf-8').write(
        f'{ahora:%d/%m/%Y %H:%M} · {ok} rutas OK · {okc} cerros OK · {len(errores)} errores\n\n' + '\n'.join(errores))
    open(os.path.join(AQUI, 'site', 'index.html'), 'w', encoding='utf-8').write(
        '<!doctype html><meta charset="utf-8"><title>Pronósticos Cumbres Digitales</title>'
        f'<p>Imágenes de pronóstico por ruta, actualizadas {ahora:%d/%m/%Y %H:%M}. '
        'Datos: <a href="https://open-meteo.com/">Open-Meteo.com</a> (CC BY 4.0). '
        '<a href="https://cumbresdigitales.wordpress.com/">Cumbres Digitales</a></p>')
    print(f'{ok} imágenes generadas')


if __name__ == '__main__':
    main()
