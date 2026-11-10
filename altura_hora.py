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


NOTAS = [('Excelente', (40, 170, 80)), ('Buena', (130, 195, 70)), ('Regular', (225, 190, 60)),
         ('Mala', (235, 130, 50)), ('Muy mala', (210, 50, 50))]


PLURAL = ['excelentes', 'buenas', 'regulares', 'malas', 'muy malas']


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
        self.G = [[v or 0 for v in x['hourly']['wind_gusts_10m'][:nh]] for x in d]
        self.dir = [v or 0 for v in d[-1]['hourly']['wind_direction_10m'][:nh]]
        self.dir_base = [v or 0 for v in d[0]['hourly']['wind_direction_10m'][:nh]]
        self.sens = [v if v is not None else 0 for v in d[-1]['hourly']['apparent_temperature'][:nh]]
        self.lluvia_h = [x['hourly']['precipitation'] for x in d]
        self.lluvia = [max(x['hourly']['precipitation'][h] or 0 for x in d) for h in range(nh)]
        self.wcode = [max(x['hourly']['weather_code'][h] or 0 for x in d) for h in range(nh)]
        self.sol = {t: (int(a[11:13]) + int(a[14:16]) / 60, int(b[11:13]) + int(b[14:16]) / 60)
                    for t, a, b in zip(d[-1]['daily']['time'], d[-1]['daily']['sunrise'], d[-1]['daily']['sunset'])}
        self.a0, self.a1 = self.alts[0], self.alts[-1]

    def nota_hora(self, h):
        """0 excelente · 1 bueno · 2 regular · 3 malo · 4 muy malo (peor condición en toda la ruta)."""
        g = self.raf[h]; p = self.lluvia[h]; w = self.wcode[h]; t = self.T[-1][h]
        sens = t - 0.2 * g  # aproximación simple de sensación térmica en la cumbre
        if w >= 95 or g > 80 or self.nieve[h] >= 1.5: return 4
        tmax = max(self.T[i][h] for i in range(len(self.alts)))  # calor: el punto más caluroso de la ruta
        if g > 60 or p >= 0.5 or sens < -15 or tmax >= 35: return 3
        if g > 45 or p > 0 or tmax >= 32 or w in (71, 73, 75, 85, 86, 61, 63, 65, 80, 81, 82): return 2
        if g > 30: return 1
        return 0

    def mejor_franja(self, fecha, horas_ruta):
        """Mejor ventana de luz del largo de la ruta: (nota, hora_inicio, hora_fin) o None."""
        if not horas_ruta: return None
        sale, pone = self.sol.get(fecha, (7, 19))
        idx = [j for j, h in enumerate(self.horas) if h[:10] == fecha]
        dur = max(1, round(horas_ruta)); mejor = None
        for i0 in range(len(idx) - dur + 1):
            hi = int(self.horas[idx[i0]][11:13])
            if hi < sale - 0.25 or hi + dur > pone + 0.25: continue
            nota = max(self.nota_hora(idx[i0 + k]) for k in range(dur))
            if mejor is None or nota < mejor[0]: mejor = (nota, hi, hi + dur)
        return mejor

    def viento(self, h, umbral=60):
        g = [self.G[i][h] for i in range(len(self.alts))]
        if max(g) < umbral: return None
        if min(g) >= umbral: return 'abajo'
        for i in range(len(self.alts) - 1):
            if g[i] < umbral <= g[i + 1]:
                return self.alts[i] + (self.alts[i + 1] - self.alts[i]) * (umbral - g[i]) / ((g[i + 1] - g[i]) or 1)
        return None

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
    # curva de ráfagas en la cumbre con escala propia a la derecha (0-100 km/h)
    vy = lambda v: y1 - min(v, 100) / 100 * (y1 - y0)
    pts = [(x0 + (h - h0 + 0.5) * (x1 - x0) / (h1 - h0), vy(D.raf[h])) for h in range(h0, h1)]
    if len(pts) > 1:
        g.line(pts, fill=(20, 20, 20), width=5)
        g.line(pts, fill=(255, 120, 60), width=3)
    for v, c in ((0, (70, 170, 90)), (30, (225, 190, 60)), (60, (225, 70, 60)), (90, (225, 70, 60))):
        y = vy(v); g.line((x1, y, x1 + 4, y), fill=c, width=2)
        g.text((x1 + 6, y - 7), f'{v}', font=fuente(11), fill=c)
    g.text((x1 + 2, y0 - 2 - 13), 'km/h', font=fuente(10), fill=(255, 140, 80))
    # escala de altura: guías cada 250 m
    paso = 250 if a1 - a0 <= 2000 else 500
    for a in range((int(a0) // paso + 1) * paso, int(a1), paso):
        y = y1 - (a - a0) / (a1 - a0) * (y1 - y0)
        cerca = min(a - a0, a1 - a) < (a1 - a0) * 0.09
        for xx in range(int(x0), int(x1), 6): g.point((xx, y), fill=(255, 255, 255))
        g.line((x0 - 4, y, x0, y), fill=(200, 200, 200))
        if not cerca: g.text((x0 - 32, y - 7), f'{a}', font=fuente(11), fill=(170, 170, 170))
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
    g.text((14, y), '— 0 °C (punteada: no hiela en la ruta)', font=FS, fill=(230, 230, 230))
    g.line((262, y + 7, 290, y + 7), fill=(255, 120, 60), width=3)
    g.text((296, y), 'ráfagas en la cumbre (escala derecha, km/h)', font=FS, fill=(255, 150, 100))
    y += 18; x = 14
    g.text((x, y), 'Condiciones:', font=FS, fill=(200, 200, 200)); x += 4 + g.textlength('Condiciones:', font=FS)
    for nombre, c in NOTAS:
        g.rectangle((x, y + 2, x + 10, y + 12), fill=c); g.text((x + 13, y), nombre, font=FS, fill=(200, 200, 200))
        x += 22 + g.textlength(nombre, font=FS)
    g.text((x + 4, y), '* nieve', font=FS, fill=(220, 240, 255))
    y += 18; x = 14
    g.text((x, y), 'Franja de viento:', font=FS, fill=(200, 200, 200)); x += 6 + g.textlength('Franja de viento:', font=FS)
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
    W, H = 600, 500
    F, FB, FS = fuente(13), fuente(17, True), fuente(12)
    g_im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(g_im)
    cumbre = 'cumbre' if ruta['tipo'] == 'Cumbre' else 'p. alto'
    g.text((14, 8), ruta['nombre'][:44], font=FB, fill=(240, 240, 240))
    g.text((14, 30), 'Próximos 7 días en toda la ruta · condiciones pronosticadas en la mejor franja de luz', font=FS, fill=(170, 170, 170))
    x0, x1, y0, y1 = 58, W - 34, 118, 308
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
        g.text((xc - g.textlength(lab, font=F) / 2, y0 - 34), lab, font=F, fill=(235, 235, 235) if i < 2 else (200, 200, 200) if i < 5 else (160, 160, 160))
        s = f'{round(max(tc))}°/{round(min(tc))}°'; g.text((xc - g.textlength(s, font=FS) / 2, y0 - 18), s, font=FS, fill=(170, 210, 255))
        s = f'{round(max(tb))}°/{round(min(tb))}°'; g.text((xc - g.textlength(s, font=FS) / 2, y1 - 16), s, font=FS, fill=(25, 25, 25))
        mf = D.mejor_franja(fe, ruta.get('horas'))
        if mf:
            nombre, c = NOTAS[mf[0]]; t1 = nombre; t2 = f'{mf[1]}-{mf[2]} h'
            g.rounded_rectangle((xc - cw / 2 + 3, y0 - 58, xc + cw / 2 - 3, y0 - 38), radius=5, fill=c)
            g.text((xc - g.textlength(t1, font=FS) / 2, y0 - 56), t1, font=FS, fill=(20, 20, 20))
            g.text((xc - g.textlength(t2, font=FS) / 2, y0 - 72), t2, font=FS, fill=(200, 200, 200))
        nv = sum(D.nieve[j] for j in hs)
        if nv >= 0.5: g.text((xc - 20, y0 + 4), f'* {nv:.0f} cm', font=FS, fill=(255, 255, 255), stroke_width=2, stroke_fill=(40, 60, 110))
    franja_viento(g, D, x0, y1 + 4, x1, 0, nh, FS)
    for i, fe in enumerate(fechas):
        hs = [j for j, h in enumerate(D.horas) if h[:10] == fe]; rm = max(D.raf[j] for j in hs)
        xc = x0 + (i + 0.5) * cw; s = f'máx {round(rm)}'
        g.text((xc - g.textlength(s, font=FS) / 2, y1 + 5), s, font=FS, fill=(20, 20, 20))
    g.text((4, y1 + 5), 'viento', font=FS, fill=(200, 200, 200))
    g.text((x0, y1 + 24), f"franja = {ruta.get('horas') or '?'} h de recorrido con luz · arriba máx/mín cumbre, abajo largada", font=FS, fill=(150, 150, 150))
    leyendas(g, W, y1 + 46, F, FS)
    g.text((14, H - 50), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo", font=FS, fill=(150, 150, 150))
    marca(g_im, (x0, y0, x1, y1)).save(destino, optimize=True)


def detalle_png(ruta, D, ahora, destino):
    W, H = 600, 668
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
        x0, x1, y0, y1 = 58, W - 34, y + 60, y + 200
        for hh in range(24):
            xa = x0 + hh * (x1 - x0) / 24; xb = x0 + (hh + 1) * (x1 - x0) / 24
            g.rectangle((xa, y0 - 14, xb - 1, y0 - 4), fill=NOTAS[D.nota_hora(h0 + hh)][1])
        mf = D.mejor_franja(fe, ruta.get('horas'))
        if mf:
            xa = x0 + mf[1] * (x1 - x0) / 24; xb = x0 + mf[2] * (x1 - x0) / 24
            g.rectangle((xa, y0 - 16, xb, y0 - 2), outline=(255, 255, 255), width=2)
            txt = f"Mejor franja {mf[1]}–{mf[2]} h: condiciones {PLURAL[mf[0]]}"
            g.text((14, y + 30), txt, font=F, fill=NOTAS[mf[0]][1])
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
    g.text((14, H - 50), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo", font=FS, fill=(150, 150, 150))
    for c in cajas: im = marca(im, c)
    im.save(destino, optimize=True)


PUNTOS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO']


def rumbo(grados):
    return PUNTOS[int((grados % 360) / 45 + 0.5) % 8]


def flecha(g, cx, cy, grados, largo=7, color=(20, 20, 20)):
    import math
    a = math.radians(grados + 180)  # hacia dónde sopla
    dx, dy = math.sin(a) * largo, -math.cos(a) * largo
    g.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=color, width=2)
    px, py = cx + dx, cy + dy; b = math.radians(25)
    for s_ in (1, -1):
        ang = a + math.pi + s_ * b
        g.line((px, py, px + math.sin(ang) * 5, py - math.cos(ang) * 5), fill=color, width=2)


def resumen(D, h0, h1, sale, pone):
    """Texto corto del día armado a partir de los datos horarios."""
    def tramo(hs):
        if not hs: return ''
        a, b = hs[0] - h0, hs[-1] - h0 + 1
        if b - a >= 20: return 'todo el día'
        nombre = lambda x: 'la madrugada' if x < 6 else 'la mañana' if x < 12 else 'la tarde' if x < 19 else 'la noche'
        return f'de {a} a {b} h' if b - a <= 6 else f'desde {nombre(a)} hasta {nombre(b - 1)}' if nombre(a) != nombre(b - 1) else f'durante {nombre(a)}'
    frases = []
    nieve = [h for h in range(h0, h1) if D.nieve[h] > 0.05]
    lluvia = [h for h in range(h0, h1) if D.lluvia[h] > 0.1 and D.nieve[h] <= 0.05]
    tormenta = [h for h in range(h0, h1) if D.wcode[h] >= 95]
    fuerte = [h for h in range(h0, h1) if D.raf[h] >= 60]
    if tormenta: frases.append('Tormentas ' + tramo(tormenta))
    if nieve: frases.append(('Nevadas débiles ' if sum(D.nieve[h] for h in nieve) < 2 else 'Nevadas ') + tramo(nieve))
    if lluvia: frases.append('Lluvia ' + tramo(lluvia))
    if not (tormenta or nieve or lluvia):
        nub = sum(1 for h in range(h0, h1) if D.wcode[h] >= 3)
        frases.append('Despejado' if nub < 5 else 'Nubosidad variable, sin precipitación' if nub < 15 else 'Nublado, sin precipitación')
    tcal = max(max(D.T[i][h0:h1]) for i in range(len(D.alts)))
    if tcal >= 32:
        calor = [h for h in range(h0, h1) if max(D.T[i][h] for i in range(len(D.alts))) >= 32]
        frases.append(f'calor fuerte (hasta {round(tcal)} °C) ' + tramo(calor) + '; llevá agua extra')
    if fuerte: frases.append('ráfagas fuertes en la cumbre ' + tramo(fuerte))
    else: frases.append('viento moderado' if max(D.raf[h0:h1]) >= 30 else 'poco viento')
    noche = [h for h in range(h0, h1) if int(D.horas[h][11:13]) < 7]
    if noche:
        dn = D.dir_base[noche[len(noche) // 2]]
        frases.append(f'de noche, abajo, viento del {rumbo(dn)}')
    t = '. '.join(f[0].upper() + f[1:] for f in frases[:1]) + ('; ' + '; '.join(frases[1:]) if len(frases) > 1 else '') + '.'
    return t


NIEVE_C = (71, 73, 75, 77, 85, 86)
LLUVIA_C = (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82)
TEXTO = {0: 'despejado', 1: 'despejado', 2: 'parcial', 3: 'nublado', 45: 'niebla', 48: 'niebla',
         95: 'tormenta', 96: 'granizo', 99: 'granizo'}


def simbolo(g, cx, cy, code, de_noche, s=9):
    """Ícono simple del tiempo de la hora: sol/luna, nube, lluvia, nieve, rayos, granizo."""
    nube = lambda: (g.ellipse((cx - s, cy - s * 0.4, cx + s * 0.2, cy + s * 0.5), fill=(185, 190, 200)),
                    g.ellipse((cx - s * 0.4, cy - s * 0.8, cx + s, cy + s * 0.5), fill=(205, 210, 220)))
    if code in (0, 1):
        if de_noche:
            g.ellipse((cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7), fill=(220, 220, 170))
            g.ellipse((cx - s * 0.3, cy - s * 0.9, cx + s, cy + s * 0.5), fill=(26, 28, 34))
        else:
            g.ellipse((cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7), fill=(250, 200, 60))
        return
    if code == 2:
        c = (220, 220, 170) if de_noche else (250, 200, 60)
        g.ellipse((cx - s * 0.2, cy - s, cx + s, cy + s * 0.2), fill=c)
    nube()
    if code in LLUVIA_C:
        for dx in (-s * 0.5, 0, s * 0.5): g.line((cx + dx, cy + s * 0.6, cx + dx - 2, cy + s * 1.1), fill=(90, 160, 255), width=2)
    if code in NIEVE_C:
        for dx in (-s * 0.5, s * 0.4): g.text((cx + dx - 3, cy + s * 0.3), '*', font=fuente(12, True), fill=(255, 255, 255))
    if code >= 95:
        g.polygon([(cx, cy + s * 0.3), (cx - 3, cy + s * 0.9), (cx, cy + s * 0.9), (cx - 2, cy + s * 1.4), (cx + 4, cy + s * 0.7), (cx + 1, cy + s * 0.7), (cx + 3, cy + s * 0.3)],
                  fill=(255, 220, 40))
    if code in (96, 99):
        for dx in (-s * 0.6, s * 0.6): g.ellipse((cx + dx - 1.5, cy + s * 0.8, cx + dx + 1.5, cy + s * 1.1), fill=(255, 255, 255))


def dia_png(ruta, D, ahora, k, destino):
    """Un día completo, hora por hora, en toda la ruta."""
    W, H = 600, 630
    F, FB, FS, FG = fuente(13), fuente(17, True), fuente(12), fuente(22, True)
    im = Image.new('RGB', (W, H), (30, 30, 30)); g = ImageDraw.Draw(im)
    cumbre = 'cumbre' if ruta['tipo'] == 'Cumbre' else 'p. alto'
    fechas = sorted({h[:10] for h in D.horas})[:DIAS]
    fe = fechas[k]; dd = datetime.date.fromisoformat(fe)
    h0, h1 = k * 24, k * 24 + 24
    sale, pone = D.sol.get(fe, (7, 19))
    g.text((14, 8), ruta['nombre'][:44], font=FB, fill=(240, 240, 240))
    nom = ('Hoy' if k == 0 else 'Mañana' if k == 1 else CORTA[dd.weekday()].capitalize()) + f' {dd:%d/%m}'
    g.text((14, 32), nom, font=FG, fill=(90, 170, 255))
    conf = 'confiable' if k < 2 else 'aceptable' if k < 5 else 'solo tendencia: puede cambiar'
    g.text((14 + g.textlength(nom, font=FG) + 10, 42), f'día {k + 1} de {DIAS} · {conf}', font=FS,
           fill=(140, 180, 220) if k < 2 else (200, 170, 90) if k < 5 else (200, 120, 90))
    nv = sum(D.nieve[h0:h1]); ll = sum(D.lluvia[h0:h1]); rm = max(D.raf[h0:h1])
    tor = any(c >= 95 for c in D.wcode[h0:h1]); gra = any(c in (96, 99) for c in D.wcode[h0:h1])
    partes = [f'ráfagas en la cumbre hasta {round(rm)} km/h']
    if nv >= 0.5: partes.append(f'nieve {nv:.0f} cm')
    elif ll >= 0.5: partes.append(f'lluvia {ll:.0f} mm')
    if gra: partes.append('granizo')
    elif tor: partes.append('tormenta eléctrica')
    g.text((14, 64), ' · '.join(partes).capitalize(), font=F, fill=(255, 130, 120) if rm >= 60 or tor else (210, 210, 210))
    import textwrap
    for j, linea in enumerate(textwrap.wrap(resumen(D, h0, h1, sale, pone), 88)[:3]):
        g.text((14, 84 + j * 16), linea, font=FS, fill=(225, 225, 225))
    mf = D.mejor_franja(fe, ruta.get('horas'))
    if mf:
        g.text((14, 134), f"Mejor franja {mf[1]}–{mf[2]} h: condiciones {PLURAL[mf[0]]}", font=F, fill=NOTAS[mf[0]][1])
    x0, x1 = 58, W - 34
    X = lambda hh: x0 + hh * (x1 - x0) / 24
    # fila 1: calificación por hora
    yb = 160
    g.text((4, yb - 1), 'condic.', font=fuente(11), fill=(170, 170, 170))
    for hh in range(24): g.rectangle((X(hh), yb, X(hh + 1) - 1, yb + 10), fill=NOTAS[D.nota_hora(h0 + hh)][1])
    if mf: g.rectangle((X(mf[1]), yb - 2, X(mf[2]), yb + 12), outline=(255, 255, 255), width=2)
    # fila 2: símbolos del tiempo
    ys = 188
    g.text((4, ys - 6), 'tiempo', font=fuente(11), fill=(170, 170, 170))
    for hh in range(24):
        noche = hh + 0.5 < sale or hh + 0.5 > pone
        if noche: g.rectangle((X(hh), ys - 12, X(hh + 1), ys + 14), fill=(26, 28, 34))
        simbolo(g, (X(hh) + X(hh + 1)) / 2, ys, D.wcode[h0 + hh], noche, 7)
    # fila 3: precipitación (mm/h, barras)
    yp0, yp1 = 208, 228
    g.text((4, yp0 + 3), 'precip.', font=fuente(11), fill=(170, 170, 170))
    g.rectangle((x0, yp0, x1, yp1), fill=(38, 40, 46))
    for hh in range(24):
        h = h0 + hh; mm = D.lluvia[h]
        if mm > 0:
            alto = min(1, mm / 3) * (yp1 - yp0)
            c = (235, 240, 255) if D.nieve[h] > 0 else (90, 160, 255)
            g.rectangle((X(hh) + 2, yp1 - alto, X(hh + 1) - 2, yp1), fill=c)
            if mm >= 0.5: g.text((X(hh) + 1, yp0 - 1), f'{mm:.0f}', font=fuente(10), fill=(220, 230, 255))
    # panel principal: temperatura por altura, 0 °C y ráfagas
    y0, y1 = 242, 392
    panel(g, D, x0, y0, x1, y1, h0, h1, 3)
    ejes_altura(g, D, 4, y0, y1, FS, cumbre)
    for hh in range(1, 24, 3):
        h = h0 + hh; x = (X(hh) + X(hh + 1)) / 2
        for i, yy in ((len(D.alts) - 1, y0 + 4), (0, y1 - 18)):
            t = D.T[i][h]; tx = f'{round(t)}°'
            g.text((x - g.textlength(tx, font=F) / 2, yy), tx, font=F, fill=(15, 15, 15) if t > -4 else (240, 240, 240))
    franja_viento(g, D, x0, y1 + 4, x1, h0, h1, FS)
    g.rectangle((x0, y1 + 20, x1, y1 + 38), fill=(42, 44, 50))
    for hh in range(1, 24, 3):
        h = h0 + hh; x = (X(hh) + X(hh + 1)) / 2
        tx = f'{round(D.raf[h])}'; g.text((x - g.textlength(tx, font=FS) / 2, y1 + 5), tx, font=FS, fill=(20, 20, 20))
        flecha(g, x - 9, y1 + 29, D.dir[h], 6, (230, 230, 230))
        g.text((x - 1, y1 + 22), rumbo(D.dir[h]), font=FS, fill=(230, 230, 230))
        st = D.sens[h]; tx = f'{round(st)}°'
        g.text((x - g.textlength(tx, font=F) / 2, y1 + 42), tx, font=F, fill=(150, 200, 255) if st < 0 else (230, 230, 230))
    g.text((4, y1 + 5), 'ráfagas', font=fuente(11), fill=(200, 200, 200))
    g.text((4, y1 + 23), 'viene del', font=fuente(11), fill=(200, 200, 200))
    g.text((4, y1 + 43), 'sensación', font=fuente(11), fill=(200, 200, 200))
    for hh in (0, 3, 6, 9, 12, 15, 18, 21):
        g.text((X(hh) - 6, y1 + 62), f'{hh}h', font=FS, fill=(170, 170, 170))
    g.text((x0, y1 + 78), 'Viento y sensación térmica en la cumbre. "Viene del": dirección de la que sopla (útil para orientar la carpa).', font=fuente(11), fill=(150, 150, 150))
    leyendas(g, W, y1 + 98, F, FS)
    g.text((14, H - 50), f"cumbresdigitales.wordpress.com · Open-Meteo · actualizado {ahora:%d/%m %H:%M} · orientativo", font=FS, fill=(150, 150, 150))
    marca(im, (x0, y0, x1, y1)).save(destino, optimize=True)


def altura_hora(ruta, perfil, ahora, carpeta):
    import os
    D = Datos(perfil)
    n = f"{ruta['n']:03d}"
    sub = os.path.join(carpeta, n); os.makedirs(sub, exist_ok=True)
    semana_png(ruta, D, ahora, os.path.join(sub, 'semana.png'))
    for k in range(DIAS):
        dia_png(ruta, D, ahora, k, os.path.join(sub, f'dia{k + 1}.png'))
    return D
