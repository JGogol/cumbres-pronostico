"""Perfil meteorológico animado: el perfil de elevación de la ruta coloreado por la
temperatura pronosticada en cada km, con la altura desde donde hiela, nieve y ráfagas.
Un cuadro de día (máxima entre 9 y 18 h) y otro de noche (mínima entre 0 y 8 h) por cada uno
de los próximos 7 días. Datos: Open-Meteo, pedidos a la altura real de cada punto del track."""
import json, os, datetime, urllib.request, urllib.parse
from PIL import Image, ImageDraw
from pronostico import fuente, TZ, CORTA, tenue

DIAS_PRONO = 7


def pedir_puntos(pts):
    q = {'latitude': ','.join(str(p[1]) for p in pts), 'longitude': ','.join(str(p[2]) for p in pts),
         'elevation': ','.join(str(p[3]) for p in pts),
         'hourly': 'temperature_2m,wind_gusts_10m,snowfall,freezing_level_height',
         'timezone': TZ, 'forecast_days': DIAS_PRONO, 'wind_speed_unit': 'kmh'}
    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'cumbres-digitales-pronostico'}), timeout=120))
    return r if isinstance(r, list) else [r]


ESC = [(-20, (40, 60, 160)), (-10, (60, 110, 210)), (0, (110, 175, 230)), (8, (120, 200, 170)),
       (16, (175, 215, 110)), (24, (240, 200, 70)), (32, (240, 120, 50))]


def col(t):
    if t <= ESC[0][0]: return ESC[0][1]
    for (a, ca), (b, cb) in zip(ESC, ESC[1:]):
        if t <= b:
            f = (t - a) / (b - a); return tuple(int(x + (y - x) * f) for x, y in zip(ca, cb))
    return ESC[-1][1]


def marca(im, caja):
    """Marca de agua 'Cumbres Digitales' semitransparente sobre el gráfico."""
    from PIL import Image as _I, ImageDraw as _D
    capa = _I.new('RGBA', im.size, (0, 0, 0, 0)); d = _D.Draw(capa)
    f = fuente(34, True); t = 'Cumbres Digitales'
    w = d.textlength(t, font=f); x0, y0, x1, y1 = caja
    d.text(((x0 + x1 - w) / 2, (y0 + y1) / 2 + 10), t, font=f, fill=(255, 255, 255, 38))
    return _I.alpha_composite(im.convert('RGBA'), capa).convert('RGB')


def interp(km, xs, ys):
    if km <= xs[0]: return ys[0]
    for i in range(len(xs) - 1):
        if xs[i] <= km <= xs[i + 1]:
            f = 0 if xs[i + 1] == xs[i] else (km - xs[i]) / (xs[i + 1] - xs[i]); return ys[i] + (ys[i + 1] - ys[i]) * f
    return ys[-1]


def perfil_gif(ruta, perfil, ahora, destino):
    P = perfil['puntos']
    # puntos de pronóstico: ~1 por km, más la largada y el punto más alto
    paso = max(1, round(len(P) / max(2, P[-1][0])))
    idx = sorted(set(list(range(0, len(P), paso)) + [len(P) - 1, max(range(len(P)), key=lambda i: P[i][3])]))
    FP = [P[i] for i in idx]
    datos = []
    for i in range(0, len(FP), 25):
        datos += pedir_puntos(FP[i:i + 25])
    horas = datos[0]['hourly']['time']
    fechas = sorted({h[:10] for h in horas})[:DIAS_PRONO]
    W, H = 600, 360
    L, R, T, B = 52, W - 18, 120, 300
    kmax = P[-1][0]; amin = min(p[3] for p in P); amax = max(p[3] for p in P)
    pad = max(150, (amax - amin) * 0.25); a0, a1 = amin - pad * 0.4, amax + pad
    X = lambda km: L + km / kmax * (R - L)
    Y = lambda a: B - (a - a0) / (a1 - a0) * (B - T)
    F, FB, FS, FG = fuente(14), fuente(18, True), fuente(12), fuente(26, True)
    ik = max(range(len(P)), key=lambda i: P[i][3])
    frames, dur = [], []
    for k, fe in enumerate(fechas):
        for modo in ('dia', 'noche'):
            rng = range(9, 19) if modo == 'dia' else range(0, 9)
            sel = [j for j, h in enumerate(horas) if h[:10] == fe and int(h[11:13]) in rng]
            temp = [(max if modo == 'dia' else min)(d['hourly']['temperature_2m'][j] for j in sel) for d in datos]
            raf = [max(d['hourly']['wind_gusts_10m'][j] or 0 for j in sel) for d in datos]
            niev = [sum(d['hourly']['snowfall'][j] or 0 for j in sel) for d in datos]
            xs = [p[0] for p in FP]
            # altura desde donde hay bajo cero, según las mismas temperaturas del perfil (ajuste lineal t vs altura)
            alts = [p[3] for p in FP]
            n_ = len(alts); ma = sum(alts) / n_; mt = sum(temp) / n_
            sxx = sum((a - ma) ** 2 for a in alts) or 1
            pend = sum((a - ma) * (t - mt) for a, t in zip(alts, temp)) / sxx
            if max(temp) < 0: hiela = 'todo'
            elif min(temp) > 0: hiela = 'nada'
            else: hiela = ma - mt / pend if pend < 0 else None
            f = 1.0 if k < 2 else 0.85 if k < 5 else 0.7
            im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(im)
            # cielo de noche más oscuro
            g.rectangle((L, T - 8, R, B), fill=(36, 42, 52) if modo == 'dia' else (22, 24, 34))
            # perfil coloreado por temperatura
            for c in range(int(L), int(R) + 1):
                km = (c - L) / (R - L) * kmax
                alt = interp(km, [p[0] for p in P], [p[3] for p in P])
                t = interp(km, xs, temp)
                g.line((c, Y(alt), c, B), fill=tenue(col(t), f))
            g.line([(X(p[0]), Y(p[3])) for p in P], fill=(235, 235, 235), width=2)
            if hiela == 'todo':
                g.text((L + 6, T - 2), 'bajo cero en todo el recorrido', font=FS, fill=(170, 220, 255))
            elif hiela == 'nada':
                g.text((L + 6, T - 2), 'sin heladas en el recorrido', font=FS, fill=(200, 200, 200))
            elif hiela is not None and a0 < hiela < a1:
                y = Y(hiela)
                for xx in range(int(L), int(R), 12): g.line((xx, y, xx + 6, y), fill=(150, 210, 255), width=2)
                g.text((L + 6, y - 16), f'bajo cero arriba de {round(hiela, -2):.0f} m', font=FS, fill=(170, 220, 255))
            # nieve y ráfagas fuertes sobre el perfil
            for j, p in enumerate(FP):
                x = X(p[0]); y = Y(p[3])
                if niev[j] >= 0.3: g.text((x - 4, y - 24), '*', font=FB, fill=(220, 240, 255))
                if raf[j] >= 60:
                    g.polygon([(x - 5, y - 30), (x + 7, y - 33), (x + 7, y - 27)], fill=(240, 90, 90))
                    g.line((x - 5, y - 30, x - 5, y - 14), fill=(240, 90, 90), width=2)
            # etiquetas: largada y punto más alto
            for i0, nom in ((0, 'Largada'), (ik, 'Cumbre' if ruta['tipo'] == 'Cumbre' else 'Punto más alto')):
                p = P[i0]; t = interp(p[0], xs, temp); x = X(p[0]); y = Y(p[3])
                tx = f"{round(t)}°"; tw = g.textlength(tx, font=FB)
                xx = min(max(x - tw / 2, L), R - tw)
                g.text((xx, y - (58 if i0 == ik else 34)), tx, font=FB, fill=col(t), stroke_width=2, stroke_fill=(20, 20, 20))
            # ejes
            for a in range(int(a0 // 500 * 500 + 500), int(a1), 500):
                g.text((6, Y(a) - 7), f'{a}', font=FS, fill=(130, 130, 130))
            for kk in range(0, int(kmax) + 1, max(1, int(kmax // 7) or 1)):
                g.text((X(kk) - 4, B + 4), f'{kk}', font=FS, fill=(150, 150, 150))
            g.text((R - 18, B + 18), 'km', font=FS, fill=(150, 150, 150))
            # encabezado
            dd = datetime.date.fromisoformat(fe)
            nom = ('Hoy' if k == 0 else 'Mañana' if k == 1 else CORTA[dd.weekday()].capitalize()) + f' {dd:%d/%m}'
            g.text((14, 8), ruta['nombre'][:44] + ' · clima en la ruta', font=FB, fill=(240, 240, 240))
            g.text((14, 36), nom, font=FG, fill=(90, 170, 255))
            g.text((14 + g.textlength(nom, font=FG) + 12, 46), 'de día (máxima)' if modo == 'dia' else 'de noche (mínima)',
                   font=F, fill=(240, 210, 120) if modo == 'dia' else (170, 170, 230))
            rmax = max(raf)
            info = f"Ráfagas hasta {round(rmax)} km/h" + (f" · nieve {max(niev):.0f} cm" if max(niev) >= 0.5 else '')
            g.text((14, 78), info, font=F, fill=(255, 110, 110) if rmax >= 60 else (210, 210, 210))
            conf = 'confiable' if k < 2 else 'aceptable' if k < 5 else 'tendencia'
            g.text((R - g.textlength(conf, font=FS), 82), conf, font=FS, fill=(140, 180, 220) if k < 2 else (200, 170, 90) if k < 5 else (200, 120, 90))
            g.text((14, H - 22), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo",
                   font=FS, fill=(150, 150, 150))
            im = marca(im, (L, T, R, B))
            frames.append(im.convert('P', palette=Image.ADAPTIVE, colors=160)); dur.append(2000 if k < 2 else 1400)
    frames[0].save(destino, save_all=True, append_images=frames[1:], duration=dur, loop=0, optimize=True)
