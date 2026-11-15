// =====================================================================
// Aralkum & Zhamanshin: Earth analogs for Mars - public map app
// NASA Space Apps Challenge 2026
//
// Data:
//   - JRC Global Surface Water v1.4 Yearly History (Landsat 5/7/8, 30 m, 1984-2021)
//     Pekel et al. 2016, Nature 540, 418-422. Source: EC JRC/Google
//   - NASADEM (NASA, 30 m) and Copernicus GLO-30 DEM (ESA, 30 m)
//   - EMIT L2B mineral results (NASA) are analysed offline; see the project report
//   - JRC Global Surface Water v1.4 transitions (global drying-lake search)
//
// Use of AI: this code was drafted with help from Claude (Anthropic AI assistant);
// run, checked and modified by the team.
// =====================================================================

// ---------------- Aral Sea: lake retreat and re-flooding ----------------
var roi = ee.Geometry.Rectangle([58.0, 43.3, 61.9, 46.9]);
var SEA_LEVEL_1960 = 53.4;
var MIN_WATER_YEARS = 3;

var copDem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM');
var basin = copDem.filterBounds(roi).mosaic().lt(SEA_LEVEL_1960).clip(roi);
var gsw = ee.ImageCollection('JRC/GSW1_4/YearlyHistory').filterBounds(roi);

function yearWhere(cond) {
  return gsw.map(function (img) {
    var y = ee.Number(img.get('year'));
    return ee.Image.constant(y).toInt16().rename('year').updateMask(cond(img));
  });
}
var lastWater = yearWhere(function (i) { return i.select('waterClass').gte(2); }).max();
var lastPermanent = yearWhere(function (i) { return i.select('waterClass').eq(3); }).max();
var waterCount = gsw.map(function (i) {
  return i.select('waterClass').gte(2).rename('n');
}).sum();
var formerSea = basin.and(waterCount.gte(MIN_WATER_YEARS));

var lakeRetreat = lastPermanent.add(1)
  .updateMask(lastPermanent.lt(2021)).updateMask(formerSea);
var refloodCount = gsw.map(function (img) {
  var y = ee.Image.constant(ee.Number(img.get('year')));
  return img.select('waterClass').gte(2).and(y.gt(lastPermanent)).rename('n');
}).sum().updateMask(lakeRetreat.mask());
var stillWater = lastWater.eq(2021).and(basin);
var neverWater = waterCount.unmask(0).eq(0).and(basin);

// ---------------- Zhamanshin impact structure ----------------
var LON0 = 60.967, LAT0 = 48.400;
var zCenter = ee.Geometry.Point([LON0, LAT0]);
var zRegion = zCenter.buffer(26000);
var nasadem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var dist = ee.FeatureCollection([ee.Feature(zCenter)]).distance(27000);
var ll = ee.Image.pixelLonLat();
var x = ll.select('longitude').subtract(LON0)
  .multiply(111320 * Math.cos(LAT0 * Math.PI / 180));
var y = ll.select('latitude').subtract(LAT0).multiply(110540);
// remove the regional tilt: plane fitted on the 18-25 km ring
var fit = ee.Image.constant(1).addBands(x).addBands(y).addBands(nasadem)
  .updateMask(dist.gt(18000).and(dist.lt(25000)))
  .reduceRegion({reducer: ee.Reducer.linearRegression(3, 1),
                 geometry: zRegion, scale: 90, maxPixels: 1e9});
var k = ee.Array(fit.get('coefficients')).project([0]);
var plane = ee.Image.constant(k.get([0]))
  .add(x.multiply(k.get([1]))).add(y.multiply(k.get([2])));
var anomaly = nasadem.subtract(plane).clip(zCenter.buffer(25000));
var ring135 = ee.Image().paint(ee.FeatureCollection([ee.Feature(zCenter.buffer(6750))]), 0, 2);
var ring265 = ee.Image().paint(ee.FeatureCollection([ee.Feature(zCenter.buffer(13250))]), 0, 2);
var emitBox = ee.Image().paint(ee.FeatureCollection(
  [ee.Feature(ee.Geometry.Rectangle([59.5, 44.6, 61.3, 45.4]))]), 0, 2);


// ---------------- Ground that never flooded again (datable surface) ----------------
var stayedDry = refloodCount.eq(0).selfMask();

// ---------------- Field route (field_route.csv in the repository) ----------------
var STOPS = [
  [1, 59.8836, 45.3330, '2015-2021', 'salt-type label 47%'],
  [2, 59.9294, 45.2339, '2005-2014', 'clays 37%, gypsum 32%'],
  [3, 60.3541, 45.0350, '1995-2004', 'clays 57%'],
  [4, 60.8381, 44.9951, '1985-1994', 'clays 60%, gypsum 10%, carbonate 4%']
];
var stopFc = ee.FeatureCollection(STOPS.map(function (s) {
  return ee.Feature(ee.Geometry.Point([s[1], s[2]]), {stop: s[0]});
}));
var routeLine = ee.FeatureCollection([ee.Feature(ee.Geometry.LineString(
  STOPS.map(function (s) { return [s[1], s[2]]; })))]);

// ---------------- Global search (step4 + step6 in the repository) ----------------
var gswAll = ee.Image('JRC/GSW1_4/GlobalSurfaceWater');
var lostPermanent = gswAll.select('transition').eq(3).selfMask();
// name, lon, lat, ground left 1985-2021 (km2), share that never flooded again
var LAKES = [
  ['Aral Sea', 59.95, 45.10, 35258, 0.38],
  ['Sistan Hamun lakes', 61.60, 30.60, 3443, 0.11],
  ['Great Salt Lake', -112.55, 41.20, 3002, 0.05],
  ['Lake Poopo', -67.10, -18.75, 2981, 0.07],
  ['Lake Urmia', 45.52, 37.65, 2648, 0.01],
  ['Torey lakes', 115.65, 50.05, 842, 0.18],
  ['Colhue Huapi', -68.85, -45.50, 748, 0.19],
  ['Malheur-Harney lakes', -119.00, 43.30, 624, 0.08],
  ['Laguna Salada', -115.65, 32.35, 520, 0.02],
  ['Carson Sink', -118.50, 39.90, 494, 0.01],
  ['Lake Aksehir', 31.45, 38.55, 262, 0.40]
];
var lakeFc = ee.FeatureCollection(LAKES.map(function (l) {
  return ee.Feature(ee.Geometry.Point([l[1], l[2]]), {name: l[0]});
}));

// ---------------- Map ----------------
var RETREAT_PAL = ['08306b', '2171b5', '6baed6', 'fdae6b', 'e6550d', 'a50f15'];
var REFLOOD_PAL = ['ffffff', 'c6dbef', '6baed6', '2171b5', '08306b'];
var ANOM_PAL = ['2166ac', '67a9cf', 'f7f7f7', 'ef8a62', 'b2182b'];

var map = ui.Map();
map.setOptions('SATELLITE');
map.setControlVisibility({drawingToolsControl: false});
map.addLayer(neverWater.selfMask(), {palette: ['ffff99']},
  'Aral: in 1960 basin, never water 1984-2021', true, 0.5);
map.addLayer(lakeRetreat, {min: 1985, max: 2021, palette: RETREAT_PAL},
  'Aral: year the permanent lake left');
map.addLayer(refloodCount, {min: 0, max: 8, palette: REFLOOD_PAL},
  'Aral: number of re-flood years after retreat', false);
map.addLayer(stillWater.selfMask(), {palette: ['00ffff']}, 'Aral: still water in 2021');
map.addLayer(stayedDry, {palette: ['1b7837']}, 'Aral: dried and never flooded again (known age)', false);
map.addLayer(lostPermanent, {palette: ['ff3d00']}, 'World: permanent water that became land 1984-2021', false);
map.addLayer(lakeFc.style({color: 'ff3d00', pointSize: 7, width: 2, fillColor: 'ffffff88'}), {}, 'World: top drying lakes', false);
map.addLayer(routeLine.style({color: '000000', width: 3}), {}, 'Aral: field route');
map.addLayer(stopFc.style({color: 'ffffff', pointSize: 8, fillColor: 'eb6834', width: 2}), {}, 'Aral: field route stops');
map.addLayer(emitBox, {palette: ['ffff00']}, 'Aral: area of the EMIT mineral analysis', false);
map.addLayer(ee.Terrain.hillshade(nasadem).clip(zRegion), {min: 150, max: 255},
  'Zhamanshin: hillshade (NASADEM)');
map.addLayer(anomaly, {min: -30, max: 30, palette: ANOM_PAL},
  'Zhamanshin: elevation anomaly, tilt removed (m)', true, 0.6);
map.addLayer(ring135, {palette: ['ffff00']}, 'Zhamanshin: classic estimate, 13.5 km');
map.addLayer(ring265, {palette: ['ff00ff']}, 'Zhamanshin: 2026 preprint, 26.5 km');
map.centerObject(roi, 7);

// ---------------- Side panel ----------------
function h(text) {
  return ui.Label(text, {fontWeight: 'bold', fontSize: '15px', margin: '12px 8px 2px 8px'});
}
function p(text) {
  return ui.Label(text, {fontSize: '13px', margin: '2px 8px', whiteSpace: 'pre-wrap'});
}
function colorBar(palette, min, max, caption) {
  var bar = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0),
    params: {bbox: [0, 0, 1, 0.1], dimensions: '200x12', format: 'png',
             min: 0, max: 1, palette: palette},
    style: {stretch: 'horizontal', margin: '4px 8px 0 8px', maxHeight: '14px'}
  });
  var ends = ui.Panel([
    ui.Label(String(min), {fontSize: '11px', margin: '0 8px'}),
    ui.Label(caption, {fontSize: '11px', margin: '0', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(max), {fontSize: '11px', margin: '0 8px'})
  ], ui.Panel.Layout.flow('horizontal'));
  return ui.Panel([bar, ends]);
}
function swatch(color, text) {
  return ui.Panel([
    ui.Label('', {backgroundColor: color, padding: '7px', margin: '4px 6px 0 8px',
                  border: '1px solid #888'}),
    ui.Label(text, {fontSize: '12px', margin: '3px 0'})
  ], ui.Panel.Layout.flow('horizontal'));
}

var panel = ui.Panel({style: {width: '360px'}});
panel.add(ui.Label('A sea that became a Martian lakebed',
  {fontWeight: 'bold', fontSize: '19px', margin: '10px 8px 2px 8px'}));
panel.add(p('The dried Aral Sea (Aralkum, Kazakhstan and Uzbekistan) as a dated analog for ' +
  'drying Martian lakes, tested on Mars, plus the Zhamanshin impact structure. ' +
  'NASA Space Apps Challenge 2026.'));
panel.add(ui.Panel([
  ui.Button('Go to Aral Sea', function () { map.centerObject(roi, 7); }),
  ui.Button('Go to Zhamanshin', function () { map.centerObject(zCenter, 10); })
], ui.Panel.Layout.flow('horizontal')));

panel.add(h('Aral Sea: when each part of the seabed dried'));
panel.add(colorBar(RETREAT_PAL, 1985, 2021, 'year the permanent lake left'));
panel.add(swatch('#ffff99', 'in the 1960 basin, never water 1984-2021'));
panel.add(swatch('#00ffff', 'still water in 2021'));
panel.add(p(
  '- Basin below the 1960 sea level (53.4 m): 68,206 km2\n' +
  '- Seabed left by the permanent lake, 1985-2021: 34,964 km2\n' +
  '- Of that, flooded again in a later year: 21,052 km2 (60%)\n' +
  '- Still water in 2021: 7,793 km2'));
panel.add(p('Turn on the "re-flood years" layer (Layers, top right) to see where the ' +
  'seabed dried and flooded again, like a playa.'));
panel.add(colorBar(REFLOOD_PAL, 0, '8+', 're-flood years after retreat'));


panel.add(swatch('#1b7837', 'dried and never flooded again: 13,380 km2 of known age (layer off by default)'));

panel.add(h('Minerals follow the drying date (NASA EMIT, 12 scenes)'));
panel.add(p('Carbonate and clay where the sea left first, gypsum in the middle, salts last. ' +
  'Clays fall in 12 of 12 scenes, the salt-type label rises in 11 of 11. Published field work ' +
  'agrees on carbonate and salts.'));

panel.add(h('Field route: 4 stops, 90 km, 36 years of drying'));
STOPS.forEach(function (s) {
  panel.add(ui.Button({
    label: 'Stop ' + s[0] + ': dried ' + s[3] + ' (' + s[4] + ')',
    onClick: function () { map.setCenter(s[1], s[2], 13); },
    style: {margin: '2px 8px', stretch: 'horizontal'}
  }));
});
panel.add(p('Each stop is a 1 km patch on ground that dried in one period and never flooded ' +
  'again. Coordinates in field_route.csv. Not visited on the ground.'));

panel.add(h('Global search: where else did a salt lake dry out?'));
panel.add(p('Every dry-climate river basin from 52S to 52N, ranked by permanent water that ' +
  'became land since 1984. The Aral ranks first. Pick a lake (turn on the "World" layers):'));
var lakeSelect = ui.Select({
  items: LAKES.map(function (l) {
    return {label: l[0] + ': ' + l[3].toLocaleString() + ' km2 left, ' +
                   Math.round(l[4] * 100) + '% never flooded again', value: l[0]};
  }),
  placeholder: 'Choose a drying lake',
  onChange: function (v) {
    LAKES.forEach(function (l) { if (l[0] === v) { map.setCenter(l[1], l[2], 9); } });
  },
  style: {stretch: 'horizontal', margin: '4px 8px'}
});
panel.add(lakeSelect);
panel.add(p('Only the Aral leaves a large surface of known age: 37 times more ground that ' +
  'never flooded again than the next lake. Most others are salt flats that flood again.'));

panel.add(h('Tested on Mars (NASA MOLA, 642 salt deposits)'));
panel.add(p('Martian chloride deposits sit in closed lows (60% vs 38% of nearby ground), but not ' +
  'in the last-to-dry part where the Aral puts salts (20% vs 23% by chance). Most Martian ' +
  'salts probably formed in small ponds, not in one big drying lake.'));

panel.add(h('Zhamanshin: can 30 m data see the rim?'));
panel.add(colorBar(ANOM_PAL, -30, 30, 'elevation anomaly (m)'));
panel.add(swatch('#ffff00', 'classic size estimate: 13.5 km diameter'));
panel.add(swatch('#ff00ff', '2026 preprint estimate: 26.5 km diameter'));
panel.add(p('The center is a high (about +75 m), not a bowl, and no clear ring shows at ' +
  '13.25 km radius in 30 m data. The larger estimate relies on 2 m elevation data.'));

panel.add(h('Limits'));
panel.add(p('Years with poor Landsat coverage (1984, 1985, 1988, 1990, 1995, 1997) make ' +
  'early retreat years less certain. Yearly water maps include seasonal and flood water. ' +
  'Earth cannot reproduce Mars gravity, atmosphere or radiation.'));

panel.add(h('Data and credits'));
panel.add(p('Water history: JRC Global Surface Water v1.4 from NASA/USGS Landsat ' +
  '(Source: EC JRC/Google). Elevation: NASADEM (NASA), Copernicus GLO-30 (ESA). ' +
  'Minerals (in the report): NASA EMIT L2B. Mars: NASA MOLA and Mars Odyssey THEMIS ' +
  'chloride map. Full report: github.com/sanim-science/aralkum-analog'));
panel.add(p('Use of AI: code drafted with help from Claude (Anthropic AI assistant); ' +
  'run and checked by the team.'));

ui.root.clear();
ui.root.add(ui.SplitPanel({firstPanel: panel, secondPanel: map}));
