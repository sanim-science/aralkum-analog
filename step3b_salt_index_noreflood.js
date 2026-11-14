// =====================================================================
// Step 3b: same Landsat check, ONLY on seabed that never re-flooded after the lake left
//
// Question: do simple surface indices from Landsat change with the year the
// Aral seabed dried, over the WHOLE basin and in three different summers?
// If yes, the EMIT result does not depend on two EMIT scenes.
//
// Indices (all are proxies, none identifies a mineral):
//   SI         = sqrt(blue * red)          salinity/brightness index, salt crusts are bright
//   NDSI_salt  = (red - nir) / (red + nir) normalised salinity index
//   SWIR_ratio = swir1 / swir2             higher where clays, carbonates, gypsum absorb near 2.2 um
//   NDVI       = (nir - red) / (nir + red) plant cover (a control, not a result)
//
// Data: Landsat 8/9 Collection 2 Level 2 surface reflectance (NASA/USGS),
//       June-September median for 2022, 2023, 2024.
//       Drying year from JRC Global Surface Water (as in step 1).
//
// AI disclosure: code drafted with help from Claude (Anthropic AI assistant);
// run, checked and modified by the team.
// =====================================================================

var roi = ee.Geometry.Rectangle([58.0, 43.3, 61.9, 46.9]);
var SEA_LEVEL_1960 = 53.4;
var MIN_WATER_YEARS = 3;
var OBS_YEARS = [2022, 2023, 2024];
var SCALE = 300;

// ---- drying year (same as step 1) ----
var basin = ee.ImageCollection('COPERNICUS/DEM/GLO30').filterBounds(roi)
  .select('DEM').mosaic().lt(SEA_LEVEL_1960).clip(roi);
var gsw = ee.ImageCollection('JRC/GSW1_4/YearlyHistory').filterBounds(roi);
var lastPermanent = gsw.map(function (img) {
  var y = ee.Number(img.get('year'));
  return ee.Image.constant(y).toInt16().rename('year')
    .updateMask(img.select('waterClass').eq(3));
}).max();
var waterCount = gsw.map(function (i) {
  return i.select('waterClass').gte(2).rename('n');
}).sum();
var lakeRetreat = lastPermanent.add(1)
  .updateMask(lastPermanent.lt(2021))
  .updateMask(basin.and(waterCount.gte(MIN_WATER_YEARS)))
  .rename('year');

// ---- keep only seabed that never re-flooded after the lake left ----
var refloodCount = gsw.map(function (img) {
  var y = ee.Image.constant(ee.Number(img.get('year')));
  return img.select('waterClass').gte(2).and(y.gt(lastPermanent)).rename('n');
}).sum();
lakeRetreat = lakeRetreat.updateMask(refloodCount.eq(0));

// ---- Landsat 8/9 summer composite ----
function prep(img) {
  var qa = img.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 1).eq(0)      // dilated cloud
    .and(qa.bitwiseAnd(1 << 3).eq(0))          // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));         // cloud shadow
  var sr = img.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
                      ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
    .multiply(0.0000275).add(-0.2);
  return sr.updateMask(clear);
}
function composite(year) {
  var l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2');
  var l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2');
  return l8.merge(l9).filterBounds(roi)
    .filterDate(year + '-06-01', year + '-09-30')
    .map(prep).median();
}
var NAMES = ['SI', 'NDSI_salt', 'SWIR_ratio', 'NDVI'];
function indices(c) {
  var si = c.select('blue').multiply(c.select('red')).sqrt().rename('SI');
  var ndsi = c.normalizedDifference(['red', 'nir']).rename('NDSI_salt');
  var swir = c.select('swir1').divide(c.select('swir2')).rename('SWIR_ratio');
  var ndvi = c.normalizedDifference(['nir', 'red']).rename('NDVI');
  var mndwi = c.normalizedDifference(['green', 'swir1']);
  // keep dry, valid land only (no open water at the time of the image)
  var ok = mndwi.lt(0).and(c.select('red').gt(0)).and(c.select('swir2').gt(0));
  return si.addBands(ndsi).addBands(swir).addBands(ndvi).updateMask(ok);
}

// ---- mean of each index for every drying year, in each observed summer ----
var all = ee.FeatureCollection([]);
OBS_YEARS.forEach(function (oy) {
  var idx = indices(composite(oy));
  var grouped = idx.addBands(lakeRetreat).reduceRegion({
    reducer: ee.Reducer.mean().repeat(NAMES.length)
      .group({groupField: NAMES.length, groupName: 'year'}),
    geometry: roi, scale: SCALE, maxPixels: 1e10, tileScale: 4
  });
  var fc = ee.FeatureCollection(ee.List(grouped.get('groups')).map(function (g) {
    g = ee.Dictionary(g);
    var m = ee.List(g.get('mean'));
    return ee.Feature(null, {
      year: g.get('year'), obs_year: 'summer ' + oy,
      SI: m.get(0), NDSI_salt: m.get(1), SWIR_ratio: m.get(2), NDVI: m.get(3)
    });
  }));
  all = all.merge(fc);
});

NAMES.forEach(function (name) {
  print(ui.Chart.feature.groups(all, 'year', name, 'obs_year')
    .setChartType('LineChart')
    .setOptions({
      title: name + ' vs. year the seabed dried (never re-flooded ground, Landsat 8/9)',
      hAxis: {title: 'Year the permanent lake left', format: '####'},
      vAxis: {title: name},
      pointSize: 3
    }));
});

// ---- map: 2023 composite and indices ----
var c2023 = composite(2023);
var i2023 = indices(c2023).updateMask(lakeRetreat.mask());
Map.centerObject(roi, 7);
Map.addLayer(c2023.clip(roi), {bands: ['red', 'green', 'blue'], min: 0, max: 0.5},
  'Landsat summer 2023, true colour');
Map.addLayer(i2023.select('SI'), {min: 0.1, max: 0.5,
  palette: ['3b2f2f', 'a67c52', 'f2e6c9', 'ffffff']}, 'SI (salinity/brightness), 2023', false);
Map.addLayer(i2023.select('SWIR_ratio'), {min: 1.0, max: 1.6,
  palette: ['2166ac', 'f7f7f7', 'b2182b']}, 'SWIR ratio, 2023', false);

Export.table.toDrive({collection: all, description: 'aral_landsat_indices_noreflood',
                      fileFormat: 'CSV'});
