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

app.listen(port, function () {
    console.log('Listening on port:' + port);
});

emulator.onDisplay(function (digits, points) {
    var msg = {
        action: 'display',
        digits: digits,
        points: points
    };
    broadcast(msg);
});
