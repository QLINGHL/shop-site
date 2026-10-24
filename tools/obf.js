const obf = require('javascript-obfuscator');
const fs = require('fs');

const input = process.argv[2];
const output = process.argv[3];
const code = fs.readFileSync(input, 'utf8');

const result = obf.obfuscate(code, {
  compact: true,
  controlFlowFlattening: true,
  controlFlowFlatteningThreshold: 0.75,
  deadCodeInjection: true,
  deadCodeInjectionThreshold: 0.4,
  debugProtection: true,
  debugProtectionInterval: 2000,
  disableConsoleOutput: true,
  identifierNamesGenerator: 'hexadecimal',
  renameGlobals: false,
  selfDefending: true,
  stringArray: true,
  stringArrayThreshold: 0.75,
  stringArrayEncoding: ['base64'],
  transformObjectKeys: true,
  unicodeEscapeSequence: false
});

let out = result.getObfuscatedCode();
// 防止 </script> 提前闭合标签
out = out.split('</script>').join('<\\/script>');
fs.writeFileSync(output, out);
console.log('obfuscated bytes:', out.length);
