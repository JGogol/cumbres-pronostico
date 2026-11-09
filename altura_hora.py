"""Gráfico altura × hora (estilo meteograma de montaña) para los próximos 7 días.
Eje x: horas; eje y: altura entre la largada y el punto más alto de la ruta; color: temperatura.
Arriba, la semana completa (para ver ventanas de buen tiempo); abajo, cada día ampliado (animado).
Línea blanca: altura de 0 °C. Asteriscos: nieve. Marcas rojas: ráfagas fuertes en la cumbre.
Datos: Open-Meteo, pedidos a la altura real de puntos del track."""
import datetime
from PIL import Image, ImageDraw
from pronostico import fuente, CORTA
from perfil_clima import pedir_puntos, marca

ESC2 = [(-20, (35, 40, 120)), (-10, (45, 85, 200)), (-4, (70, 140, 230)), (0, (150, 210, 245)),
        (4, (120, 200, 150)), (10, (175, 215, 95)), (18, (240, 200, 70)), (28, (240, 120, 50))]


def col(t):
    if t <= ESC2[0][0]: return ESC2[0][1]
    for (a, ca), (b, cb) in zip(ESC2, ESC2[1:]):
        if t <= b:
            f = (t - a) / (b - a); return tuple(int(x + (y - x) * f) for x, y in zip(ca, cb))
    return ESC2[-1][1]

DIAS = 7


def niveles(perfil, n=9):
    P = perfil['puntos']
    ik = max(range(len(P)), key=lambda i: P[i][3])
    subida = P[:ik + 1] if ik > 0 else P
    amin, amax = min(p[3] for p in subida), P[ik][3]
    out = []
    for j in range(n):
        objetivo = amin + (amax - amin) * j / (n - 1)
        p = min(subida, key=lambda q: abs(q[3] - objetivo))
        if not out or p[3] > out[-1][3]: out.append(p)
    return out


def tabla(datos, var):
    return [[v if v is not None else 0 for v in d['hourly'][var]] for d in datos]


def altura_hora_gif(ruta, perfil, ahora, destino):
    N = niveles(perfil)
    datos = pedir_puntos(N)
    horas = datos[0]['hourly']['time'][:DIAS * 24]
    TT = [r[:DIAS * 24] for r in tabla(datos, 'temperature_2m')]
    SN = tabla(datos, 'snowfall')[-1][:DIAS * 24]
    GU = tabla(datos, 'wind_gusts_10m')[-1][:DIAS * 24]
    alts = [p[3] for p in N]; a0, a1 = alts[0], alts[-1]
    nh = len(horas)
    W, H = 600, 430
    F, FB, FS, FG = fuente(14), fuente(17, True), fuente(12), fuente(24, True)

    def temp_en(h, a):
        if a <= alts[0]: return TT[0][h]
        for i in range(len(alts) - 1):
            if alts[i] <= a <= alts[i + 1]:
                f = (a - alts[i]) / ((alts[i + 1] - alts[i]) or 1); return TT[i][h] + (TT[i + 1][h] - TT[i][h]) * f
        return TT[-1][h]

    def cero(h):  # altura de 0 °C en la hora h (None si no cruza dentro del rango)
        col_t = [TT[i][h] for i in range(len(alts))]
        if min(col_t) > 0: return 'arriba'
        if max(col_t) < 0: return 'abajo'
        for i in range(len(alts) - 1):
            t0, t1 = col_t[i], col_t[i + 1]
            if (t0 >= 0 > t1) or (t0 < 0 <= t1):
                return alts[i] + (alts[i + 1] - alts[i]) * (t0 / (t0 - t1))
        return None

    def mapa(g, x0, y0, x1, y1, h0, h1, paso_px):
        for h in range(h0, h1):
            xa = x0 + (h - h0) * (x1 - x0) / (h1 - h0); xb = x0 + (h - h0 + 1) * (x1 - x0) / (h1 - h0)
            for py in range(int(y0), int(y1), paso_px):
                a = a1 - (py - y0) / (y1 - y0) * (a1 - a0)
                g.rectangle((xa, py, xb, py + paso_px), fill=col(temp_en(h, a)))
        # línea de 0 °C
        pts = []
        for h in range(h0, h1):
            z = cero(h); x = x0 + (h - h0 + 0.5) * (x1 - x0) / (h1 - h0)
            if isinstance(z, (int, float)): pts.append((x, y1 - (z - a0) / (a1 - a0) * (y1 - y0)))
            else:
                if len(pts) > 1: g.line(pts, fill=(255, 255, 255), width=2)
                pts = []
        if len(pts) > 1: g.line(pts, fill=(255, 255, 255), width=2)
        # separadores de día
        for h in range(h0, h1):
            if horas[h][11:13] == '00' and h != h0:
                x = x0 + (h - h0) * (x1 - x0) / (h1 - h0); g.line((x, y0, x, y1), fill=(20, 20, 20), width=2)

    # ---- franja semanal
    SX0, SX1, SY0, SY1 = 50, W - 14, 58, 128
    fechas = sorted({h[:10] for h in horas})[:DIAS]
    frames, dur = [], []
    for k, fe in enumerate(fechas):
        im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(im)
        g.text((14, 8), ruta['nombre'][:42] + ' · temperatura por altura y hora', font=FB, fill=(240, 240, 240))
        g.text((14, 32), 'Semana completa: buscá las ventanas de buen tiempo', font=FS, fill=(170, 170, 170))
        mapa(g, SX0, SY0, SX1, SY1, 0, nh, 3)
        for i, f2 in enumerate(fechas):
            dd = datetime.date.fromisoformat(f2)
            x = SX0 + (i + 0.5) * (SX1 - SX0) / DIAS
            g.text((x - 14, SY1 + 3), f"{CORTA[dd.weekday()]} {dd:%d}", font=FS, fill=(230, 230, 230) if i == k else (140, 140, 140))
        # nieve / viento en la franja
        for h in range(nh):
            x = SX0 + (h + 0.5) * (SX1 - SX0) / nh
            if SN[h] >= 0.1: g.ellipse((x - 1.5, SY0 - 7, x + 1.5, SY0 - 4), fill=(220, 240, 255))
            if GU[h] >= 60: g.line((x, SY0 - 3, x, SY0 - 1), fill=(240, 80, 80))
        xa = SX0 + k * (SX1 - SX0) / DIAS; xb = SX0 + (k + 1) * (SX1 - SX0) / DIAS
        g.rectangle((xa, SY0 - 2, xb, SY1 + 1), outline=(255, 255, 255), width=2)
        g.text((6, SY0 - 2), f'{a1}', font=FS, fill=(150, 150, 150)); g.text((6, SY1 - 13), f'{a0}', font=FS, fill=(150, 150, 150))
        # ---- día ampliado
        DX0, DX1, DY0, DY1 = 56, W - 14, 214, 356
        dd = datetime.date.fromisoformat(fe)
        nom = ('Hoy' if k == 0 else 'Mañana' if k == 1 else CORTA[dd.weekday()].capitalize()) + f' {dd:%d/%m}'
        g.text((14, 148), nom, font=FG, fill=(90, 170, 255))
        conf = 'confiable' if k < 2 else 'aceptable' if k < 5 else 'tendencia: puede cambiar'
        g.text((14 + g.textlength(nom, font=FG) + 12, 158), conf, font=FS,
               fill=(140, 180, 220) if k < 2 else (200, 170, 90) if k < 5 else (200, 120, 90))
        h0 = k * 24; h1 = min(h0 + 24, nh)
        mapa(g, DX0, DY0, DX1, DY1, h0, h1, 4)
        for h in range(h0, h1):
            x = DX0 + (h - h0 + 0.5) * (DX1 - DX0) / (h1 - h0)
            if SN[h] >= 0.1: g.text((x - 4, DY0 - 16), '*', font=FB, fill=(220, 240, 255))
            if GU[h] >= 60:
                g.polygon([(x - 3, DY0 - 2), (x + 3, DY0 - 2), (x, DY0 - 9)], fill=(240, 80, 80))
        for hh in (0, 6, 9, 12, 15, 18, 21):
            x = DX0 + hh * (DX1 - DX0) / 24
            g.line((x, DY1, x, DY1 + 4), fill=(150, 150, 150)); g.text((x - 6, DY1 + 6), f'{hh}h', font=FS, fill=(170, 170, 170))
        # alturas
        for a, et in ((a0, 'largada'), (a1, 'cumbre' if ruta['tipo'] == 'Cumbre' else 'p. alto')):
            y = DY1 - (a - a0) / (a1 - a0) * (DY1 - DY0)
            yy = y - 13 if a == a0 else y
            g.text((4, yy), f'{a}', font=FS, fill=(210, 210, 210))
            g.text((4, yy + (13 if a == a1 else -12)), et, font=FS, fill=(140, 140, 140))
        # números de temperatura cada 3 h en la largada y en la cumbre
        for hh in range(1, 24, 3):
            h = h0 + hh
            if h >= h1: break
            x = DX0 + (hh + 0.5) * (DX1 - DX0) / (h1 - h0)
            for i, yy in ((len(alts) - 1, DY0 + 4), (0, DY1 - 18)):
                t = TT[i][h]; tx = f'{round(t)}°'; tw = g.textlength(tx, font=F)
                g.text((x - tw / 2, yy), tx, font=F, fill=(15, 15, 15) if t > -4 else (240, 240, 240))
        tmin = min(min(TT[i][h0:h1]) for i in range(len(alts))); tmax = max(max(TT[i][h0:h1]) for i in range(len(alts)))
        rmax = max(GU[h0:h1]); nv = sum(SN[h0:h1])
        info = f"De {round(tmin)}° a {round(tmax)}°  ·  ráfagas en la cumbre hasta {round(rmax)} km/h" + (f"  ·  nieve {nv:.0f} cm" if nv >= 0.5 else '')
        g.text((14, 178), info, font=FS, fill=(255, 120, 120) if rmax >= 60 else (210, 210, 210))
        # leyenda
        LX0, LX1, LY = 230, W - 14, 382
        for x in range(LX0, LX1):
            t = -20 + (x - LX0) / (LX1 - LX0) * 50; g.line((x, LY, x, LY + 8), fill=col(t))
        for t in (-20, -10, 0, 10, 20, 30):
            x = LX0 + (t + 20) / 50 * (LX1 - LX0); g.text((x - 8, LY + 10), f'{t}°', font=FS, fill=(160, 160, 160))
        g.text((14, LY - 4), '— 0 °C   * nieve   ▲ ráfagas ≥ 60', font=FS, fill=(200, 200, 200))
        g.text((14, H - 18), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo",
               font=FS, fill=(150, 150, 150))
        im = marca(im, (DX0, DY0, DX1, DY1))
        frames.append(im.convert('P', palette=Image.ADAPTIVE, colors=200)); dur.append(2500 if k < 2 else 1800)
    frames[0].save(destino, save_all=True, append_images=frames[1:], duration=dur, loop=0, optimize=True)
