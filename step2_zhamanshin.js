// =====================================================================
// Step 2: Zhamanshin impact structure - can open 30 m elevation data
// see the crater rim(s)?
//
// Two published size estimates to test:
//   - classic estimate: ~13.5 km diameter (radius ~6.75 km)
//     (Garvin & Schnetzler 1992, NASA NTRS 19930000951)
//   - 2026 preprint: ~26.5 km multi-ring structure (radius ~13.25 km),
//     based on 2 m EarthDEM (Garvin et al. 2026, arXiv:2604.04884)
//
// Method: azimuthally averaged elevation vs distance from the center,
// after removing the regional tilt (plane fitted 18-25 km from center),
// plus the same profile for four sectors (N, E, S, W).
//
// Data: NASADEM (NASA, 30 m, from SRTM 2000) and Copernicus GLO-30 DEM (ESA).
// Center: 48.400 N, 60.967 E (Earth Impact Database).
//
// AI disclosure: code drafted with help from Claude (Anthropic AI assistant);
// run, checked and modified by the team.
// =====================================================================

var LON0 = 60.967, LAT0 = 48.400;
var R_MAX = 25000;      // m, profile out to 25 km
var BIN = 250;          // m, ring width
var center = ee.Geometry.Point([LON0, LAT0]);
var region = center.buffer(R_MAX + 1000);

var nasadem = ee.Image('NASA/NASADEM_HGT/001').select('elevation').rename('z');
var cop = ee.ImageCollection('COPERNICUS/DEM/GLO30').filterBounds(region)
  .select('DEM').mosaic().rename('z');

// distance from center (m) and local x/y (m)
var dist = ee.FeatureCollection([ee.Feature(center)])
  .distance(R_MAX + 2000).rename('dist');
var ll = ee.Image.pixelLonLat();
var x = ll.select('longitude').subtract(LON0)
  .multiply(111320 * Math.cos(LAT0 * Math.PI / 180)).rename('x');
var y = ll.select('latitude').subtract(LAT0).multiply(110540).rename('y');

// azimuth sectors: 0 = N, 1 = E, 2 = S, 3 = W
var az = x.atan2(y).multiply(180 / Math.PI).add(360).mod(360);
var sector = az.add(45).mod(360).divide(90).floor().rename('sector');

// remove regional tilt: fit z = a + b*x + c*y on the 18-25 km ring
function detrend(z) {
  var outer = dist.gt(18000).and(dist.lt(R_MAX));
  var fit = ee.Image.constant(1).rename('c').addBands(x).addBands(y).addBands(z)
    .updateMask(outer)
    .reduceRegion({reducer: ee.Reducer.linearRegression(3, 1),
                   geometry: region, scale: 90, maxPixels: 1e9});
  var k = ee.Array(fit.get('coefficients')).project([0]);
  var plane = ee.Image.constant(k.get([0]))
    .add(x.multiply(k.get([1]))).add(y.multiply(k.get([2])));
  return z.subtract(plane).rename('resid');
}
var residN = detrend(nasadem);
var residC = detrend(cop);

// radial profile: mean residual per 250 m ring
function profile(resid, label, mask) {
  var img = resid.addBands(dist.divide(BIN).floor().rename('bin'));
  if (mask) img = img.updateMask(mask);
  var g = img.reduceRegion({
    reducer: ee.Reducer.mean().group({groupField: 1, groupName: 'bin'}),
    geometry: region, scale: 30, maxPixels: 1e9, tileScale: 4
  });
  return ee.FeatureCollection(ee.List(g.get('groups')).map(function (d) {
    d = ee.Dictionary(d);
    return ee.Feature(null, {
      r_km: ee.Number(d.get('bin')).add(0.5).multiply(BIN / 1000),
      resid_m: d.get('mean'),
      series: label
    });
  })).filter(ee.Filter.lte('r_km', R_MAX / 1000));
}

var both = profile(residN, 'NASADEM').merge(profile(residC, 'Copernicus DEM'));
print(ui.Chart.feature.groups(both, 'r_km', 'resid_m', 'series')
  .setChartType('LineChart')
  .setOptions({
    title: 'Zhamanshin: mean elevation vs distance from center (regional tilt removed)',
    hAxis: {title: 'Distance from center (km)',
            viewWindow: {min: 0, max: 25}},
    vAxis: {title: 'Elevation anomaly (m)'},
    pointSize: 2
  }));

var names = ['North', 'East', 'South', 'West'];
var sectors = ee.FeatureCollection([]);
for (var s = 0; s < 4; s++) {
  sectors = sectors.merge(profile(residN, names[s], sector.eq(s)));
}
print(ui.Chart.feature.groups(sectors, 'r_km', 'resid_m', 'series')
  .setChartType('LineChart')
  .setOptions({
    title: 'Zhamanshin by sector (NASADEM, tilt removed)',
    hAxis: {title: 'Distance from center (km)', viewWindow: {min: 0, max: 25}},
    vAxis: {title: 'Elevation anomaly (m)'},
    pointSize: 2
  }));

// map
var rings = ee.FeatureCollection([
  ee.Feature(center.buffer(6750), {r: 1}),
  ee.Feature(center.buffer(13250), {r: 2})
]);
Map.centerObject(center, 10);
Map.setOptions('SATELLITE');
Map.addLayer(ee.Terrain.hillshade(nasadem), {min: 150, max: 255}, 'Hillshade (NASADEM)');
Map.addLayer(residN.clip(region), {min: -30, max: 30,
  palette: ['2166ac', '67a9cf', 'f7f7f7', 'ef8a62', 'b2182b']},
  'Elevation anomaly (tilt removed)', true, 0.6);
Map.addLayer(ee.Image().paint(rings.filter(ee.Filter.eq('r', 1)), 0, 2),
  {palette: ['ffff00']}, 'Classic estimate: 13.5 km diameter');
Map.addLayer(ee.Image().paint(rings.filter(ee.Filter.eq('r', 2)), 0, 2),
  {palette: ['ff00ff']}, '2026 preprint: 26.5 km diameter');

Export.table.toDrive({collection: both, description: 'zhamanshin_radial_profile', fileFormat: 'CSV'});
Export.table.toDrive({collection: sectors, description: 'zhamanshin_sector_profiles', fileFormat: 'CSV'});
