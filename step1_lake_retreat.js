// =====================================================================
// Aralkum analog project - Step 1 (v3): lake retreat vs. later re-flooding
//
// Why v3: v2 used "last year a pixel was water". In the shallow eastern basin
// that picks up late, temporary re-flooding (2017-2021), not when the lake
// first left. v3 separates the two:
//   - lake retreat year  = last year of PERMANENT water + 1  (waterClass 3)
//   - re-flood count     = number of later years with any water (class 2 or 3)
//
// Data:
//   - JRC Global Surface Water v1.4, Yearly History (Landsat 5/7/8, 30 m, 1984-2021)
//     Pekel et al. 2016, Nature 540, 418-422. Source: EC JRC/Google
//   - Copernicus GLO-30 DEM (ESA, 30 m) for the former sea basin outline
//
// AI disclosure: code drafted with help from Claude (Anthropic AI assistant);
// run, checked and modified by the team.
// =====================================================================

// ---- Settings ----
var roi = ee.Geometry.Rectangle([58.0, 43.3, 61.9, 46.9]);
var SEA_LEVEL_1960 = 53.4;
var MIN_WATER_YEARS = 3;
var MAX_NODATA_PCT = 5;
var SCALE = 300;

// ---- 1. Basin and water history ----
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30')
  .filterBounds(roi).select('DEM').mosaic();
var basin = dem.lt(SEA_LEVEL_1960).clip(roi);

var gsw = ee.ImageCollection('JRC/GSW1_4/YearlyHistory').filterBounds(roi);

function yearWhere(cond) {           // image = year, where cond(img) is true
  return gsw.map(function (img) {
    var y = ee.Number(img.get('year'));
    return ee.Image.constant(y).toInt16().rename('year').updateMask(cond(img));
  });
}

var lastWater = yearWhere(function (img) {
  return img.select('waterClass').gte(2);
}).max();
var lastPermanent = yearWhere(function (img) {
  return img.select('waterClass').eq(3);
}).max();

var waterCount = gsw.map(function (img) {
  return img.select('waterClass').gte(2).rename('n');
}).sum();
var formerSea = basin.and(waterCount.gte(MIN_WATER_YEARS));

// Lake retreat: first year after the last permanent-water year
var lakeRetreat = lastPermanent.add(1)
  .updateMask(lastPermanent.lt(2021)).updateMask(formerSea).rename('year');

// Re-flooding: years with any water AFTER the lake retreated
var refloodCount = gsw.map(function (img) {
  var y = ee.Image.constant(ee.Number(img.get('year')));
  return img.select('waterClass').gte(2).and(y.gt(lastPermanent)).rename('n');
}).sum().updateMask(lakeRetreat.mask()).rename('n');

var stillWater = lastWater.eq(2021).and(basin);
// JRC masks pixels that were never water, so unmask them to 0 first
var neverWater = waterCount.unmask(0).eq(0).and(basin);

// ---- 2. Map ----
Map.centerObject(roi, 7);
Map.setOptions('SATELLITE');
Map.addLayer(neverWater.selfMask(), {palette: ['ffff99']},
  'In basin, never water 1984-2021', true, 0.5);
Map.addLayer(lakeRetreat,
  {min: 1985, max: 2021,
   palette: ['08306b', '2171b5', '6baed6', 'fdae6b', 'e6550d', 'a50f15']},
  'Lake retreat year (last permanent water + 1)');
Map.addLayer(refloodCount,
  {min: 0, max: 8, palette: ['ffffff', 'c6dbef', '6baed6', '2171b5', '08306b']},
  'Number of re-flood years after retreat', false);
Map.addLayer(stillWater.selfMask(), {palette: ['00ffff']}, 'Still water in 2021');

// ---- 3. Data quality + water area per year (same as v2) ----
var areaImg = ee.Image.pixelArea().divide(1e6);
function sumArea(img, name) {
  return ee.Number(areaImg.updateMask(img).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: roi, scale: SCALE,
    maxPixels: 1e10, tileScale: 4
  }).get('area'));
}
var basinArea = sumArea(basin);

var stats = ee.FeatureCollection(gsw.map(function (img) {
  var wc = img.select('waterClass');
  var s = areaImg.updateMask(wc.gte(2)).updateMask(basin).rename('water')
    .addBands(areaImg.updateMask(wc.eq(3)).updateMask(basin).rename('permanent'))
    .addBands(areaImg.updateMask(wc.eq(0)).updateMask(basin).rename('nodata'))
    .reduceRegion({reducer: ee.Reducer.sum(), geometry: roi, scale: SCALE,
                   maxPixels: 1e10, tileScale: 4});
  return ee.Feature(null, {
    year: img.get('year'),
    water_km2: s.get('water'),
    permanent_km2: s.get('permanent'),
    nodata_pct: ee.Number(s.get('nodata')).divide(basinArea).multiply(100)
  });
}));
var goodYears = stats.filter(ee.Filter.lt('nodata_pct', MAX_NODATA_PCT));

print('Basin area below 53.4 m (km2):', basinArea);
print('Years flagged for missing data:',
  stats.filter(ee.Filter.gte('nodata_pct', MAX_NODATA_PCT)).aggregate_array('year'));

print(ui.Chart.feature.byFeature(goodYears, 'year', ['water_km2', 'permanent_km2'])
  .setChartType('LineChart')
  .setOptions({
    title: 'Aral Sea area, good-data years: any water vs permanent water (km2)',
    hAxis: {title: 'Year', format: '####'},
    vAxis: {title: 'Area (km2)'},
    pointSize: 3
  }));

// ---- 4. Area by lake retreat year, and by re-flood count ----
function groupedArea(img, field) {
  var d = areaImg.addBands(img).reduceRegion({
    reducer: ee.Reducer.sum().group({groupField: 1, groupName: field}),
    geometry: roi, scale: SCALE, maxPixels: 1e10, tileScale: 4
  });
  return ee.FeatureCollection(ee.List(d.get('groups')).map(function (g) {
    g = ee.Dictionary(g);
    var f = {};
    return ee.Feature(null, ee.Dictionary(f).set(field, g.get(field))
                                            .set('area_km2', g.get('sum')));
  }));
}

var retreatFc = groupedArea(lakeRetreat, 'year');
print(ui.Chart.feature.byFeature(retreatFc, 'year', 'area_km2')
  .setChartType('ColumnChart')
  .setOptions({
    title: 'Seabed area left by the permanent lake, per year (km2)',
    hAxis: {title: 'Lake retreat year', format: '####'},
    vAxis: {title: 'Area (km2)'}, legend: {position: 'none'}
  }));

var refloodFc = groupedArea(refloodCount, 'reflood_years');
print(ui.Chart.feature.byFeature(refloodFc, 'reflood_years', 'area_km2')
  .setChartType('ColumnChart')
  .setOptions({
    title: 'Exposed seabed by number of re-flood years after retreat (km2)',
    hAxis: {title: 'Number of later years with water'},
    vAxis: {title: 'Area (km2)'}, legend: {position: 'none'}
  }));

// ---- 5. Totals as plain numbers ----
print('Seabed left by the lake 1985-2021 (km2):', sumArea(lakeRetreat.mask()));
print('  ...of which re-flooded at least once (km2):', sumArea(refloodCount.gte(1)));
print('In basin, never water 1984-2021 (km2):', sumArea(neverWater));
print('Still water in 2021 (km2):', sumArea(stillWater));

// ---- 6. Exports ----
Export.table.toDrive({collection: stats, description: 'aral_area_quality_v3', fileFormat: 'CSV'});
Export.table.toDrive({collection: retreatFc, description: 'aral_retreat_area_by_year', fileFormat: 'CSV'});
Export.table.toDrive({collection: refloodFc, description: 'aral_reflood_area', fileFormat: 'CSV'});
// ---- 7. Raster export for the EMIT comparison ----
// Paste at the END of step1_lake_retreat, run, then start the task in the Tasks tab.
// Same box as the AppEEARS request, 60 m (EMIT pixel size), plain lat/lon grid.
// Bands: 1 = lake retreat year (0 = none)
//        2 = re-flood years after retreat (-1 = not exposed 1985-2021)
//        3 = class (0 = other, 1 = still water 2021, 2 = in basin but never water 1984-2021)
var emitBox = ee.Geometry.Rectangle([59.5, 44.6, 61.3, 45.4]);
var classImg = ee.Image(0)
  .where(neverWater.unmask(0), 2)
  .where(stillWater.unmask(0), 1)
  .rename('class');
var forEmit = lakeRetreat.unmask(0).rename('retreat_year')
  .addBands(refloodCount.unmask(-1).rename('reflood_years'))
  .addBands(classImg)
  .toInt16()
  .clip(emitBox);
Map.addLayer(emitBox, {color: 'yellow'}, 'EMIT request box', false);
Export.image.toDrive({
  image: forEmit,
  description: 'aral_retreat_for_emit_60m',
  region: emitBox,
  scale: 60,
  crs: 'EPSG:4326',
  fileFormat: 'GeoTIFF',
  maxPixels: 1e9
});
