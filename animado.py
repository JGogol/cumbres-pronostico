"""Versión animada (GIF) del pronóstico de 16 días: barras mín-máx, ráfagas y nieve, con un cursor que recorre los días."""
import datetime
from PIL import Image, ImageDraw
from pronostico import fuente, color_t, tenue, CORTA, WMO
from perfil_clima import marca

def gif(ruta, d, ahora, destino):
    D = d['daily']; H = d['hourly']; nd = len(D['time'])
    W, Hh = 600, 452                            # 30 px libres al pie para el rótulo de la galería
    L, R, T, B = 46, W - 44, 146, 248           # área de temperaturas
    VT, VB = 262, 352                           # panel de ráfagas con escala propia
    B_ = B
    tx = [v if v is not None else 0 for v in D['temperature_2m_max']]
    tn = [v if v is not None else 0 for v in D['temperature_2m_min']]
    gu = [v or 0 for v in D['wind_gusts_10m_max']]
    nv = [v or 0 for v in D['snowfall_sum']]; pr = [v or 0 for v in D['precipitation_sum']]
    lo, hi = min(tn) - 3, max(tx) + 3
    ty = lambda t: B - (t - lo) / (hi - lo) * (B - T)
    gy = lambda v: VB - min(v, 110) / 110 * (VB - VT)
    col_v = lambda v: (70, 170, 90) if v < 30 else (225, 190, 60) if v < 60 else (230, 70, 60)
    cw = (R - L) / nd; cx = lambda k: L + cw * (k + 0.5)
    F, FB, FS, FG = fuente(14), fuente(18, True), fuente(12), fuente(30, True)
    lugar = 'Cumbre' if ruta['tipo'] == 'Cumbre' else 'Punto más alto'

    def base():
        im = Image.new('RGB', (W, Hh), (30, 30, 30)); g = ImageDraw.Draw(im)
        # confiabilidad: fondo por tramos
        for k in range(nd):
            c = (40, 48, 58) if k < 2 else (36, 40, 46) if k < 7 else (32, 33, 35)
            g.rectangle((L + cw * k, T - 6, L + cw * (k + 1), VB + 2), fill=c)
        g.text((L + 2, VB + 22), 'confiable', font=FS, fill=(140, 180, 220))
        g.text((cx(2) - 6, VB + 22), 'aceptable', font=FS, fill=(200, 170, 90))
        g.text((cx(9), VB + 22), 'tendencia: puede cambiar mucho', font=FS, fill=(200, 120, 90))
        # línea de 0 °C
        # escala de temperatura (°C) a la izquierda
        g.text((L, T - 22), 'Temperatura en la ' + ('cumbre' if lugar == 'Cumbre' else 'zona más alta') + ' (°C): mínima a máxima', font=FS, fill=(170, 170, 170))
        paso = 5 if hi - lo <= 30 else 10
        for t in range(int(lo // paso * paso), int(hi) + 1, paso):
            if t < lo: continue
            y = ty(t)
            g.line((L, y, R, y), fill=(90, 120, 160) if t == 0 else (48, 52, 58))
            g.text((8, y - 7), f'{t}°', font=FS, fill=(140, 180, 220) if t == 0 else (130, 130, 130))
        for k in range(nd):
            f = 1 if k < 2 else 0.85 if k < 7 else 0.6
            x = cx(k)
            g.rounded_rectangle((x - cw * 0.28, ty(tx[k]), x + cw * 0.28, ty(tn[k])), radius=4, fill=tenue(color_t((tx[k] + tn[k]) / 2), f))
            if nv[k] >= 0.5:
                g.text((x - 4, ty(tx[k]) - 18), '*', font=FB, fill=tenue((190, 225, 255), f))
            elif pr[k] >= 0.5:
                g.text((x - 3, ty(tx[k]) - 16), "'", font=FB, fill=tenue((120, 170, 255), f))
            fe = datetime.date.fromisoformat(D['time'][k])
            g.text((x - 6, VB + 5), f"{fe:%d}", font=FS, fill=tenue((180, 180, 180), f))
        # ráfagas: panel propio con curva y escala a la derecha (0-120 km/h)
        for a, b_, c in ((0, 30, (40, 70, 48)), (30, 60, (72, 64, 36)), (60, 110, (78, 40, 38))):
            g.rectangle((L, gy(b_), R, gy(a)), fill=c)
        for v, c in ((30, (225, 190, 60)), (60, (230, 70, 60)), (90, (230, 70, 60))):
            y = gy(v)
            g.line((R, y, R + 4, y), fill=c, width=2); g.text((R + 6, y - 7), f'{v}', font=FS, fill=c)
        g.text((R + 2, VB - 10), 'km/h', font=fuente(10), fill=(170, 170, 170))
        g.text((4, VT + 30), 'ráfagas', font=fuente(11), fill=(255, 140, 80)); g.text((4, VT + 44), 'cumbre', font=fuente(11), fill=(170, 170, 170))
        pts = [(cx(k), gy(gu[k])) for k in range(nd)]
        g.line(pts, fill=(20, 20, 20), width=5)
        g.line(pts, fill=(255, 120, 60), width=2)
        for k in range(nd):
            x, y = pts[k]; f = 1 if k < 2 else 0.85 if k < 7 else 0.6
            g.ellipse((x - 4, y - 4, x + 4, y + 4), fill=tenue(col_v(gu[k]), f), outline=(20, 20, 20))
        g.text((14, 8), f"{ruta['nombre'][:30]} · 16 días · {lugar} {ruta['alt']} m", font=FB, fill=(240, 240, 240))
        g.text((14, Hh - 50), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo",
               font=FS, fill=(150, 150, 150))
        return marca(im, (L, T, R, VB))

    frames, dur = [], []
    fondo = base()
    for k in range(nd):
        im = fondo.copy(); g = ImageDraw.Draw(im); x = cx(k)
        g.rectangle((L + cw * k, T - 6, L + cw * (k + 1), VB + 2), outline=(240, 240, 240), width=2)
        fe = datetime.date.fromisoformat(D['time'][k])
        dia = ('Hoy' if k == 0 else 'Mañana' if k == 1 else CORTA[fe.weekday()].capitalize()) + f" {fe:%d/%m}"
        g.text((14, 40), dia, font=FB, fill=(90, 170, 255))
        g.text((14, 66), f"{round(tx[k])}°", font=FG, fill=color_t(tx[k]))
        g.text((80, 66), f"{round(tn[k])}°", font=FG, fill=color_t(tn[k]))
        g.text((14, 102), 'máx', font=FS, fill=(160, 160, 160)); g.text((80, 102), 'mín', font=FS, fill=(160, 160, 160))
        det = WMO.get(D['weather_code'][k], '')
        g.text((160, 44), det, font=F, fill=(220, 220, 220))
        g.text((160, 66), f"Ráfagas {round(gu[k])} km/h", font=F, fill=(255, 110, 110) if gu[k] >= 60 else (220, 220, 220))
        es_nieve = nv[k] > 0 or tx[k] <= 1 or (D['weather_code'][k] or 0) in (71, 73, 75, 77, 85, 86)
        if pr[k] >= 0.5 and es_nieve: p = f"Nieve {max(nv[k], 1):.0f} cm" if nv[k] >= 0.5 else f"Nieve débil ({pr[k]:.0f} mm de agua)"
        elif pr[k] >= 0.5: p = f"Lluvia {pr[k]:.0f} mm"
        else: p = 'Sin precipitación'
        g.text((160, 86), p, font=F, fill=(190, 225, 255) if nv[k] >= 0.5 else (220, 220, 220))
        fl = [v for t, v in zip(H['time'], H['freezing_level_height']) if t.startswith(D['time'][k]) and v is not None]
        if fl: g.text((380, 44), f"Hiela desde los {round(min(fl), -2):.0f} m", font=F, fill=(180, 210, 255))
        frames.append(im.convert('P', palette=Image.ADAPTIVE, colors=128)); dur.append(2200 if k < 2 else 1300)
    frames[0].save(destino, save_all=True, append_images=frames[1:], duration=dur, loop=0, optimize=True)
