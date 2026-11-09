"""Versión animada (GIF) del pronóstico de 16 días: barras mín-máx, ráfagas y nieve, con un cursor que recorre los días."""
import datetime
from PIL import Image, ImageDraw
from pronostico import fuente, color_t, tenue, CORTA, WMO
from perfil_clima import marca

def gif(ruta, d, ahora, destino):
    D = d['daily']; H = d['hourly']; nd = len(D['time'])
    W, Hh = 600, 360
    L, R, T, B = 46, W - 20, 146, 250           # área de temperaturas
    VT, VB = 258, 292                           # franja de ráfagas
    tx = [v if v is not None else 0 for v in D['temperature_2m_max']]
    tn = [v if v is not None else 0 for v in D['temperature_2m_min']]
    gu = [v or 0 for v in D['wind_gusts_10m_max']]
    nv = [v or 0 for v in D['snowfall_sum']]; pr = [v or 0 for v in D['precipitation_sum']]
    lo, hi = min(tn) - 3, max(tx) + 3
    ty = lambda t: B - (t - lo) / (hi - lo) * (B - T)
    gmax = max(100, max(gu))
    gy = lambda v: VB - v / gmax * (VB - VT)
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
        # ráfagas: barritas en franja propia
        g.text((4, VT + 6), 'ráf.', font=FS, fill=(235, 110, 110))
        for k in range(nd):
            f = 1 if k < 2 else 0.85 if k < 7 else 0.6
            c = (235, 80, 80) if gu[k] >= 60 else (200, 150, 150)
            g.rectangle((cx(k) - cw * 0.22, gy(gu[k]), cx(k) + cw * 0.22, VB), fill=tenue(c, f))
        g.text((14, 8), f"{ruta['nombre'][:30]} · 16 días · {lugar} {ruta['alt']} m", font=FB, fill=(240, 240, 240))
        g.text((14, Hh - 22), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo",
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
        p = f"Nieve {nv[k]:.0f} cm" if nv[k] >= 0.5 else (f"Lluvia {pr[k]:.0f} mm" if pr[k] >= 0.5 else 'Sin precipitación')
        g.text((160, 86), p, font=F, fill=(190, 225, 255) if nv[k] >= 0.5 else (220, 220, 220))
        fl = [v for t, v in zip(H['time'], H['freezing_level_height']) if t.startswith(D['time'][k]) and v is not None]
        if fl: g.text((380, 44), f"Hiela desde los {round(min(fl), -2):.0f} m", font=F, fill=(180, 210, 255))
        frames.append(im.convert('P', palette=Image.ADAPTIVE, colors=128)); dur.append(2200 if k < 2 else 1300)
    frames[0].save(destino, save_all=True, append_images=frames[1:], duration=dur, loop=0, optimize=True)
