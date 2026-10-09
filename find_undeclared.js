const fs = require('fs');
const js = fs.readFileSync('test_script_0.js', 'utf8');

// We can just run it in a mock DOM to see what fails immediately.
const { JSDOM } = require('jsdom');
const dom = new JSDOM(`<!DOCTYPE html><html><body><div id="map"></div></body></html>`, { runScripts: "dangerously" });
try {
    dom.window.eval(js);
    console.log("No synchronous errors");
} catch(e) {
    console.log("Sync error:", e);
}
