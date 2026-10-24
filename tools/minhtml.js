const { minify } = require('html-minifier-terser');
const fs = require('fs');

(async () => {
  const input = process.argv[2];
  const output = process.argv[3];
  const html = fs.readFileSync(input, 'utf8');
  const out = await minify(html, {
    collapseWhitespace: true,
    conservativeCollapse: true,
    removeComments: true,
    removeRedundantAttributes: true,
    removeEmptyAttributes: true,
    minifyCSS: true,
    minifyJS: false, // JS 已单独混淆
    keepClosingSlash: true,
    caseSensitive: true
  });
  fs.writeFileSync(output, out);
  console.log('minified bytes:', out.length);
})();
