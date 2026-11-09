"""Temperatura por altura y hora a lo largo de la ruta (estilo meteograma de montaña).
Genera dos imágenes fijas:
  NNN-semana.png  : los próximos 7 días seguidos (ventanas de buen tiempo de un vistazo)
  NNN-detalle.png : hoy y mañana, hora por hora
Eje y: altura entre la largada y el punto más alto; color: temperatura; línea blanca: altura de 0 °C
(punteada arriba cuando no hiela en ninguna parte de la ruta); franja inferior: ráfagas en la cumbre
con colores tipo semáforo. Datos: Open-Meteo, pedidos a la altura real de puntos del track."""
import datetime
from PIL import Image, ImageDraw
from pronostico import fuente, CORTA
from perfil_clima import pedir_puntos, marca

DIAS = 7
ESC2 = [(-20, (35, 40, 120)), (-10, (45, 85, 200)), (-4, (70, 140, 230)), (0, (150, 210, 245)),
        (4, (120, 200, 150)), (10, (175, 215, 95)), (18, (240, 200, 70)), (28, (240, 120, 50))]


def col(t):
    if t <= ESC2[0][0]: return ESC2[0][1]
    for (a, ca), (b, cb) in zip(ESC2, ESC2[1:]):
        if t <= b:
            f = (t - a) / (b - a); return tuple(int(x + (y - x) * f) for x, y in zip(ca, cb))
    return ESC2[-1][1]


def col_viento(v):
    return (70, 170, 90) if v < 30 else (225, 190, 60) if v < 60 else (225, 70, 60)


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


class Datos:
    def __init__(self, perfil):
        N = niveles(perfil)
        d = pedir_puntos(N)
        self.horas = d[0]['hourly']['time'][:DIAS * 24]
        nh = len(self.horas)
        self.alts = [p[3] for p in N]
        self.T = [[v if v is not None else 0 for v in x['hourly']['temperature_2m'][:nh]] for x in d]
        self.nieve = [v or 0 for v in d[-1]['hourly']['snowfall'][:nh]]
        self.raf = [v or 0 for v in d[-1]['hourly']['wind_gusts_10m'][:nh]]
        self.a0, self.a1 = self.alts[0], self.alts[-1]

    def temp(self, h, a):
        al, T = self.alts, self.T
        if a <= al[0]: return T[0][h]
        for i in range(len(al) - 1):
            if al[i] <= a <= al[i + 1]:
                f = (a - al[i]) / ((al[i + 1] - al[i]) or 1); return T[i][h] + (T[i + 1][h] - T[i][h]) * f
        return T[-1][h]

    def cero(self, h):
        c = [self.T[i][h] for i in range(len(self.alts))]
        if min(c) > 0: return 'arriba'      # no hiela en la ruta
        if max(c) < 0: return 'abajo'       # hiela en toda la ruta
        for i in range(len(self.alts) - 1):
            t0, t1 = c[i], c[i + 1]
            if (t0 >= 0 > t1) or (t0 < 0 <= t1):
                return self.alts[i] + (self.alts[i + 1] - self.alts[i]) * (t0 / (t0 - t1))
        return 'arriba' if c[-1] > 0 else 'abajo'


def panel(g, D, x0, y0, x1, y1, h0, h1, px=3):
    """Mapa altura × hora con la línea de 0 °C siempre visible."""
    a0, a1 = D.a0, D.a1
    for h in range(h0, h1):
        xa = x0 + (h - h0) * (x1 - x0) / (h1 - h0); xb = x0 + (h - h0 + 1) * (x1 - x0) / (h1 - h0)
        for py in range(int(y0), int(y1), px):
            a = a1 - (py - y0) / (y1 - y0) * (a1 - a0)
            g.rectangle((xa, py, xb, min(py + px, y1)), fill=col(D.temp(h, a)))
    prev = None
    for h in range(h0, h1):
        x = x0 + (h - h0 + 0.5) * (x1 - x0) / (h1 - h0)
        z = D.cero(h)
        if z == 'arriba': y, est = y0 + 1, 'p'
        elif z == 'abajo': y, est = y1 - 1, 'p'
        else: y, est = y1 - (z - a0) / (a1 - a0) * (y1 - y0), 's'
        if prev:
            if est == 's' and prev[2] == 's': g.line((prev[0], prev[1], x, y), fill=(255, 255, 255), width=2)
            else:
                for t in (0.0, 0.5):
                    xa = prev[0] + (x - prev[0]) * t; ya = prev[1] + (y - prev[1]) * t
                    xb = prev[0] + (x - prev[0]) * (t + 0.3); yb = prev[1] + (y - prev[1]) * (t + 0.3)
                    g.line((xa, ya, xb, yb), fill=(255, 255, 255), width=2)
        prev = (x, y, est)
    for h in range(h0 + 1, h1):
        if D.horas[h][11:13] == '00':
            x = x0 + (h - h0) * (x1 - x0) / (h1 - h0); g.line((x, y0, x, y1 + 18), fill=(25, 25, 25), width=2)


def franja_viento(g, D, x0, y0, x1, h0, h1, F, numeros_cada=None):
    alto = 16
    for h in range(h0, h1):
        xa = x0 + (h - h0) * (x1 - x0) / (h1 - h0); xb = x0 + (h - h0 + 1) * (x1 - x0) / (h1 - h0)
        g.rectangle((xa, y0, xb, y0 + alto), fill=col_viento(D.raf[h]))
    if numeros_cada:
        for h in range(h0 + 1, h1, numeros_cada):
            x = x0 + (h - h0 + 0.5) * (x1 - x0) / (h1 - h0); t = f'{round(D.raf[h])}'
            g.text((x - g.textlength(t, font=F) / 2, y0 + 1), t, font=F, fill=(20, 20, 20))


def leyendas(g, W, y, F, FS):
    g.text((14, y), '— 0 °C', font=FS, fill=(230, 230, 230))
    g.text((64, y), '- - no hiela en la ruta', font=FS, fill=(200, 200, 200))
    g.text((200, y), '* nieve', font=FS, fill=(220, 240, 255))
    x = 262
    g.text((x, y), 'Ráfagas en la cumbre:', font=FS, fill=(200, 200, 200)); x += 132
    for c, t in (((70, 170, 90), '<30'), ((225, 190, 60), '30-60'), ((225, 70, 60), '>60 km/h')):
        g.rectangle((x, y + 2, x + 10, y + 12), fill=c); g.text((x + 13, y), t, font=FS, fill=(200, 200, 200))
        x += 22 + g.textlength(t, font=FS)
    LX0, LX1 = 50, W - 14; y2 = y + 20
    for xx in range(LX0, LX1):
        t = -20 + (xx - LX0) / (LX1 - LX0) * 50; g.line((xx, y2, xx, y2 + 8), fill=col(t))
    for t in (-20, -10, 0, 10, 20, 30):
        xx = LX0 + (t + 20) / 50 * (LX1 - LX0); g.text((xx - 8, y2 + 10), f'{t}°', font=FS, fill=(160, 160, 160))


def ejes_altura(g, D, x, y0, y1, FS, cumbre):
    g.text((x, y0), f'{D.a1}', font=FS, fill=(210, 210, 210)); g.text((x, y0 + 13), cumbre, font=FS, fill=(140, 140, 140))
    g.text((x, y1 - 26), 'largada', font=FS, fill=(140, 140, 140)); g.text((x, y1 - 13), f'{D.a0}', font=FS, fill=(210, 210, 210))


def semana_png(ruta, D, ahora, destino):
    W, H = 600, 420
    F, FB, FS = fuente(13), fuente(17, True), fuente(12)
    g_im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(g_im)
    cumbre = 'cumbre' if ruta['tipo'] == 'Cumbre' else 'p. alto'
    g.text((14, 8), ruta['nombre'][:44], font=FB, fill=(240, 240, 240))
    g.text((14, 32), 'Temperatura por altura y hora · próximos 7 días · buscá las ventanas de buen tiempo', font=FS, fill=(170, 170, 170))
    x0, x1, y0, y1 = 58, W - 14, 92, 282
    nh = len(D.horas)
    panel(g, D, x0, y0, x1, y1, 0, nh, 3)
    ejes_altura(g, D, 4, y0, y1, FS, cumbre)
    fechas = sorted({h[:10] for h in D.horas})[:DIAS]
    cw = (x1 - x0) / DIAS
    for i, fe in enumerate(fechas):
        dd = datetime.date.fromisoformat(fe); xc = x0 + (i + 0.5) * cw
        hs = [j for j, h in enumerate(D.horas) if h[:10] == fe]
        tc = [D.T[-1][j] for j in hs]; tb = [D.T[0][j] for j in hs]
        lab = ('Hoy' if i == 0 else 'Mañ.' if i == 1 else CORTA[dd.weekday()]) + f' {dd:%d}'
        g.text((xc - g.textlength(lab, font=F) / 2, y0 - 36), lab, font=F, fill=(235, 235, 235) if i < 2 else (200, 200, 200) if i < 5 else (160, 160, 160))
        s = f'{round(max(tc))}°/{round(min(tc))}°'; g.text((xc - g.textlength(s, font=FS) / 2, y0 - 18), s, font=FS, fill=(170, 210, 255))
        s = f'{round(max(tb))}°/{round(min(tb))}°'; g.text((xc - g.textlength(s, font=FS) / 2, y1 - 16), s, font=FS, fill=(25, 25, 25))
        nv = sum(D.nieve[j] for j in hs)
        if nv >= 0.5: g.text((xc - 20, y0 + 4), f'* {nv:.0f} cm', font=FS, fill=(255, 255, 255), stroke_width=2, stroke_fill=(40, 60, 110))
    franja_viento(g, D, x0, y1 + 4, x1, 0, nh, FS)
    for i, fe in enumerate(fechas):
        hs = [j for j, h in enumerate(D.horas) if h[:10] == fe]; rm = max(D.raf[j] for j in hs)
        xc = x0 + (i + 0.5) * cw; s = f'máx {round(rm)}'
        g.text((xc - g.textlength(s, font=FS) / 2, y1 + 5), s, font=FS, fill=(20, 20, 20))
    g.text((4, y1 + 5), 'viento', font=FS, fill=(200, 200, 200))
    g.text((x0, y1 + 24), 'arriba: máx/mín en la cumbre · abajo: en la largada · días 6-7: solo tendencia', font=FS, fill=(150, 150, 150))
    leyendas(g, W, y1 + 46, F, FS)
    g.text((14, H - 20), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo", font=FS, fill=(150, 150, 150))
    marca(g_im, (x0, y0, x1, y1)).save(destino, optimize=True)


def detalle_png(ruta, D, ahora, destino):
    W, H = 600, 572
    cajas = []
    F, FB, FS, FG = fuente(13), fuente(17, True), fuente(12), fuente(22, True)
    im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(im)
    cumbre = 'cumbre' if ruta['tipo'] == 'Cumbre' else 'p. alto'
    g.text((14, 8), ruta['nombre'][:44], font=FB, fill=(240, 240, 240))
    g.text((14, 32), 'Temperatura por altura y hora · hoy y mañana en detalle', font=FS, fill=(170, 170, 170))
    fechas = sorted({h[:10] for h in D.horas})[:2]
    y = 56
    for k, fe in enumerate(fechas):
        dd = datetime.date.fromisoformat(fe)
        nom = ('Hoy' if k == 0 else 'Mañana') + f' {CORTA[dd.weekday()]} {dd:%d/%m}'
        g.text((14, y), nom, font=FG, fill=(90, 170, 255))
        h0, h1 = k * 24, k * 24 + 24
        nv = sum(D.nieve[h0:h1]); rm = max(D.raf[h0:h1])
        info = f"Ráfagas en la cumbre hasta {round(rm)} km/h" + (f" · nieve {nv:.0f} cm" if nv >= 0.5 else '')
        g.text((14 + g.textlength(nom, font=FG) + 12, y + 8), info, font=FS, fill=(255, 130, 120) if rm >= 60 else (210, 210, 210))
        x0, x1, y0, y1 = 58, W - 14, y + 34, y + 174
        panel(g, D, x0, y0, x1, y1, h0, h1, 3); cajas.append((x0, y0, x1, y1))
        ejes_altura(g, D, 4, y0, y1, FS, cumbre)
        for hh in range(1, 24, 3):
            h = h0 + hh; x = x0 + (hh + 0.5) * (x1 - x0) / 24
            for i, yy in ((len(D.alts) - 1, y0 + 4), (0, y1 - 18)):
                t = D.T[i][h]; s = f'{round(t)}°'
                g.text((x - g.textlength(s, font=F) / 2, yy), s, font=F, fill=(15, 15, 15) if t > -4 else (240, 240, 240))
            if D.nieve[h] >= 0.1: g.text((x - 4, y0 + 20), '*', font=FB, fill=(255, 255, 255))
        franja_viento(g, D, x0, y1 + 4, x1, h0, h1, FS, numeros_cada=3)
        g.text((4, y1 + 5), 'viento', font=FS, fill=(200, 200, 200))
        for hh in (0, 3, 6, 9, 12, 15, 18, 21):
            x = x0 + hh * (x1 - x0) / 24; g.text((x - 6, y1 + 22), f'{hh}h', font=FS, fill=(170, 170, 170))
        y = y1 + 44
    leyendas(g, W, y + 2, F, FS)
    g.text((14, H - 20), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo", font=FS, fill=(150, 150, 150))
    for c in cajas: im = marca(im, c)
    im.save(destino, optimize=True)


def altura_hora(ruta, perfil, ahora, carpeta):
    D = Datos(perfil)
    n = f"{ruta['n']:03d}"
    import os
    semana_png(ruta, D, ahora, os.path.join(carpeta, f'{n}-semana.png'))
    detalle_png(ruta, D, ahora, os.path.join(carpeta, f'{n}-detalle.png'))
