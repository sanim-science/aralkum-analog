// Step 5: repeat the Aral drying-year map on a second drying lake, so we can test
// whether the mineral order (carbonate/clay first, gypsum middle, salts last) holds
// somewhere else. Same method as step1 v3, but the lake outline comes from the
// water history itself (any pixel that was water in at least 3 years), so no
// elevation threshold is needed.
//
// Choose the lake on the next line: 'urmia' (Iran) or 'salton' (California).
var LAKE = 'urmia';
//
// Run, then in the Tasks tab start BOTH exports:
//   <lake>_retreat_for_emit_60m  (raster for the EMIT comparison)
//   <lake>_retreat_area_by_year  (table)
//
// Data: JRC Global Surface Water v1.4 Yearly History (Pekel et al. 2016, Nature 540,
// 418-422; source EC JRC/Google), from Landsat 5/7/8, 30 m, 1984-2021.
// AI disclosure: written with help from Claude (Anthropic AI assistant); run and
// checked by the team.

var BOXES = {
  urmia:  [44.95, 36.95, 46.10, 38.35],
  salton: [-116.15, 33.05, -115.55, 33.55]
};
var roi = ee.Geometry.Rectangle(BOXES[LAKE]);
var MIN_WATER_YEARS = 3;
var SCALE = 120;

var gsw = ee.ImageCollection('JRC/GSW1_4/YearlyHistory').filterBounds(roi);

function yearWhere(cond) {
  return gsw.map(function (img) {
    var y = ee.Number(img.get('year'));
    return ee.Image.constant(y).toInt16().rename('year').updateMask(cond(img));
  });
}
var lastWater = yearWhere(function (img) { return img.select('waterClass').gte(2); }).max();
var lastPermanent = yearWhere(function (img) { return img.select('waterClass').eq(3); }).max();
var waterCount = gsw.map(function (img) {
  return img.select('waterClass').gte(2).rename('n');
}).sum().unmask(0).clip(roi);

var formerLake = waterCount.gte(MIN_WATER_YEARS);

var lakeRetreat = lastPermanent.add(1)
  .updateMask(lastPermanent.lt(2021)).updateMask(formerLake).rename('year');
var refloodCount = gsw.map(function (img) {
  var y = ee.Image.constant(ee.Number(img.get('year')));
  return img.select('waterClass').gte(2).and(y.gt(lastPermanent)).rename('n');
}).sum().updateMask(lakeRetreat.mask()).rename('n');
var stillWater = lastWater.eq(2021).and(formerLake);

Map.centerObject(roi, 8);
Map.setOptions('SATELLITE');
Map.addLayer(lakeRetreat, {min: 1985, max: 2021,
  palette: ['08306b', '2171b5', '6baed6', 'fdae6b', 'e6550d', 'a50f15']},
  'Lake retreat year (last permanent water + 1)');
Map.addLayer(refloodCount, {min: 0, max: 8,
  palette: ['ffffff', 'c6dbef', '6baed6', '2171b5', '08306b']}, 'Re-flood years', false);
Map.addLayer(stillWater.selfMask(), {palette: ['00ffff']}, 'Still water in 2021');

var areaImg = ee.Image.pixelArea().divide(1e6);
function sumArea(img) {
  return ee.Number(areaImg.updateMask(img).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: roi, scale: SCALE, maxPixels: 1e10, tileScale: 4
  }).get('area'));
}
print(LAKE + ': ground that was water in at least 3 years (km2):', sumArea(formerLake));
print('Ground left by the permanent lake 1985-2021 (km2):', sumArea(lakeRetreat.mask()));
print('  ...of which re-flooded at least once (km2):', sumArea(refloodCount.gte(1)));
print('Still water in 2021 (km2):', sumArea(stillWater));

var d = areaImg.addBands(lakeRetreat).reduceRegion({
  reducer: ee.Reducer.sum().group({groupField: 1, groupName: 'year'}),
  geometry: roi, scale: SCALE, maxPixels: 1e10, tileScale: 4
});
var retreatFc = ee.FeatureCollection(ee.List(d.get('groups')).map(function (g) {
  g = ee.Dictionary(g);
  return ee.Feature(null, {year: g.get('year'), area_km2: g.get('sum')});
}));
print(ui.Chart.feature.byFeature(retreatFc, 'year', 'area_km2').setChartType('ColumnChart')
  .setOptions({title: LAKE + ': area left by the permanent lake per year (km2)',
               hAxis: {format: '####'}, legend: {position: 'none'}}));

var forEmit = lakeRetreat.unmask(0).rename('retreat_year')
  .addBands(refloodCount.unmask(-1).rename('reflood_years'))
  .addBands(ee.Image(0).where(stillWater.unmask(0), 1).rename('class'))
  .toInt16().clip(roi);

Export.image.toDrive({image: forEmit, description: LAKE + '_retreat_for_emit_60m',
  region: roi, scale: 60, crs: 'EPSG:4326', fileFormat: 'GeoTIFF', maxPixels: 1e9});
Export.table.toDrive({collection: retreatFc, description: LAKE + '_retreat_area_by_year',
  fileFormat: 'CSV'});
