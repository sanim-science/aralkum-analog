// Step 6: which drying lakes leave ground of a known age?
//
// The Aral mineral test needs ground that stayed dry after the lake left, so that
// "drying year" really is the age of the surface. Lake Urmia failed this: 99% of the
// ground its permanent lake left was flooded again later (a seasonal salt playa).
// Here we measure the same thing for the top lakes from the global search:
//   left_km2      = ground left by permanent water, 1985-2021
//   stayed_dry    = share of that ground never flooded again (any water) up to 2021
//
// Run, then in Tasks start "datable_ground" and send us the CSV
// (the Console also prints the table).
//
// Data: JRC Global Surface Water v1.4 Yearly History (Pekel et al. 2016).
// AI disclosure: written with help from Claude (Anthropic AI assistant); run and
// checked by the team.

var LAKES = [
  ['Aral Sea',               [58.0, 43.3, 61.9, 46.9]],
  ['Great Salt Lake',        [-113.2, 40.6, -111.9, 41.8]],
  ['Carson Sink',            [-118.9, 39.5, -118.1, 40.3]],
  ['Malheur-Harney lakes',   [-119.4, 43.1, -118.6, 43.5]],
  ['Lake Poopo',             [-67.5, -19.2, -66.7, -18.3]],
  ['Sistan Hamun lakes',     [60.9, 29.4, 62.3, 31.8]],
  ['Colhue Huapi',           [-69.3, -45.7, -68.4, -45.3]],
  ['Lake Urmia',             [44.95, 36.95, 46.10, 38.35]],
  ['Laguna Salada',          [-115.9, 32.0, -115.4, 32.7]],
  ['Torey lakes',            [115.2, 49.8, 116.1, 50.3]],
  ['Lake Aksehir',           [31.2, 38.4, 31.7, 38.7]]
];
var SCALE = 120;

var gsw = ee.ImageCollection('JRC/GSW1_4/YearlyHistory');
function yearWhere(cond) {
  return gsw.map(function (img) {
    return ee.Image.constant(ee.Number(img.get('year'))).toInt16().rename('year')
      .updateMask(cond(img));
  });
}
var lastPermanent = yearWhere(function (img) { return img.select('waterClass').eq(3); }).max();
var waterCount = gsw.map(function (img) {
  return img.select('waterClass').gte(2).rename('n');
}).sum().unmask(0);
var left = lastPermanent.lt(2021).and(waterCount.gte(3));   // ground left by the permanent lake
var reflood = gsw.map(function (img) {
  var y = ee.Image.constant(ee.Number(img.get('year')));
  return img.select('waterClass').gte(2).and(y.gt(lastPermanent)).rename('n');
}).sum();
var stayedDry = left.and(reflood.eq(0));
var area = ee.Image.pixelArea().divide(1e6);
var stack = area.updateMask(left).rename('left_km2')
  .addBands(area.updateMask(stayedDry).rename('dry_km2'));

var fc = ee.FeatureCollection(LAKES.map(function (l) {
  return ee.Feature(ee.Geometry.Rectangle(l[1]), {lake: l[0]});
})).map(function (f) {
  var s = stack.reduceRegion({reducer: ee.Reducer.sum(), geometry: f.geometry(),
                              scale: SCALE, maxPixels: 1e10, tileScale: 8});
  var l = ee.Number(s.get('left_km2'));
  var d = ee.Number(s.get('dry_km2'));
  return ee.Feature(null, {lake: f.get('lake'), left_km2: l, stayed_dry_km2: d,
                           stayed_dry_share: d.divide(l.max(1e-6))});
});

print('Ground left by permanent water 1985-2021, and share that stayed dry', fc);
Export.table.toDrive({collection: fc, description: 'datable_ground', fileFormat: 'CSV',
  selectors: ['lake', 'left_km2', 'stayed_dry_km2', 'stayed_dry_share']});
