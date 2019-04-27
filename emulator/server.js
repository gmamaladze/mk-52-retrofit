'use strict';

var port = process.env.PORT || 8080;

var path = require('path');
var express = require('express');
var expressWs = require('express-ws');
expressWs = expressWs(express());
var app = expressWs.app;

var emulator = require('./emulator.js');

app.use(express.static('public'));

var aWss = expressWs.getWss('/');

app.ws('/', function (ws, req) {
    console.log('Socket connected.');
    ws.onmessage = function (res) {
        console.log('Received: ' + res.data);
        var msg = JSON.parse(res.data);

        switch (msg.action) {
            case "sync":
                emulator.sync();
                break;
            case "button":
                emulator.buttonPress(msg.x, msg.y);
                break;
            case "key":
                emulator.keyPress(msg.code);
                break;
        }
    };
});

function broadcast(msg) {
    var data = JSON.stringify(msg);
    console.log('Sending: ' + data);
    aWss.clients.forEach(function (client) {
        client.send(data);
    });
}

app.get('/', function (req, res) {
    res.sendFile(path.join(__dirname + '/index.html'));
});


app.post('/ping', function (req, res) {
    res.sendStatus(200)
});

app.put('/program', function (req, res) {
    let sourceCode = req.query.code;
    emulator.push(sourceCode);
    res.sendStatus(200)
});

app.get('/program', function (req, res) {
    let sourceCode = emulator.pull();
    res.send(sourceCode)
});

app.listen(port, function () {
    console.log('Listening on port:' + port);
});

emulator.onDisplay(function (digits, points, is_dimmed) {
    var msg = {
        action: 'display',
        digits: digits,
        points: points,
        is_dimmed: is_dimmed
    };
    broadcast(msg);
});
