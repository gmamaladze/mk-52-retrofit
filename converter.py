import js2py

js = open('emulator-rom.js', 'r').read().replace("document.write", "return ")


result = js2py.translate_js(js)

f = open("emulator.py", "a")
f.write(result)
f.close()