# Cumbres Digitales · pronóstico por ruta

Genera dos veces por día una imagen con el pronóstico de hoy y mañana en el punto más alto de cada ruta de [Cumbres Digitales](https://cumbresdigitales.wordpress.com/), a la altura real de ese punto.

- `data/rutas.json`: número de ruta, nombre, latitud, longitud y altura del punto más alto.
- `pronostico.py`: pide los datos a Open-Meteo y dibuja `site/img/NNN.png`.
- `.github/workflows/pronostico.yml`: corre a las 5:00 y a las 17:00 (hora de Mendoza) y publica las imágenes en GitHub Pages.

Datos meteorológicos: [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Es un pronóstico de modelo y es orientativo: confirmalo antes de salir.
