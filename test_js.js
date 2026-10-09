const fs = require('fs');
const html = fs.readFileSync('templates/index.html', 'utf8');
const jsMatch = html.match(/<script>([\s\S]*?)<\/script>/g);
jsMatch.forEach((script, i) => {
    const js = script.replace(/<script>|<\/script>/g, '');
    fs.writeFileSync(`test_script_${i}.js`, js);
    console.log(`Extracted script ${i}`);
});
