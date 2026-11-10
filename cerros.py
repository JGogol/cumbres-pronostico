"""Pronóstico de los cerros más altos de cada provincia (página "⛅ Argentina").
Por cerro: tendencia de 16 días en la cumbre y la semana / cada día en la vertical del cerro,
desde una altura de base hasta la cumbre. Imágenes en site/img/cerros/<slug>/."""
import json, os, time, traceback, urllib.request
AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, 'site', 'img', 'cerros')
PUBLICADO = 'https://jgogol.github.io/cumbres-pronostico/img/cerros'
NOMBRES = ['semana.png'] + [f'dia{k}.png' for k in range(1, 8)] + ['tendencia.gif']


def perfil_vertical(c, n=9):
    return {'puntos': [[j, c['lat'], c['lon'], round(c['base'] + (c['alt'] - c['base']) * j / (n - 1))] for j in range(n)]}


def rescatar(slug):
    for nom in NOMBRES:
        dst = os.path.join(SALIDA, slug, nom)
        if os.path.exists(dst): continue
        try:
            b = urllib.request.urlopen(f'{PUBLICADO}/{slug}/{nom}', timeout=30).read()
            os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(b)
        except Exception:
            pass


def generar(ahora):
    from pronostico import pedir
    from animado import gif
    import altura_hora as AH
    cerros = json.load(open(os.path.join(AQUI, 'data', 'cerros.json'), encoding='utf-8'))
    ok, errores = 0, []
    for c in cerros:
        ruta = {'n': 0, 'nombre': f"{c['nombre']} ({c['prov']})", 'tipo': 'Cumbre', 'alt': c['alt'], 'lat': c['lat'], 'lon': c['lon'],
                'horas': None, 'base_txt': 'base', 'sub_semana': f"Próximos 7 días en la vertical del cerro, de {c['base']} m a la cumbre",
                'nota_semana': 'arriba: máx/mín en la cumbre · abajo: en la base · alturas según la base Montañas de Argentina'}
        carpeta = os.path.join(SALIDA, c['slug']); os.makedirs(carpeta, exist_ok=True)
        try:
            D = AH.Datos(perfil_vertical(c))
            AH.semana_png(ruta, D, ahora, os.path.join(carpeta, 'semana.png'))
            for k in range(AH.DIAS):
                AH.dia_png(ruta, D, ahora, k, os.path.join(carpeta, f'dia{k + 1}.png'))
            gif(ruta, pedir([ruta])[0], ahora, os.path.join(carpeta, 'tendencia.gif'))
            ok += 1
        except Exception:
            errores.append(f"cerro {c['nombre']}: " + traceback.format_exc().strip().splitlines()[-1]); rescatar(c['slug'])
        time.sleep(0.4)
    return ok, errores
