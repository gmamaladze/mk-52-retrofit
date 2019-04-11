'use strict';

var port = process.env.PORT || 8080;

var express = require('express'),
    emulator = require('./emulator.js'),
    faye = require('faye'),
    http = require('http'),
    path = require('path');

var app = express(),
    server = http.createServer(app),
    bayeux = new faye.NodeAdapter({mount: '/faye', timeout: 45}),
    client = new faye.Client('http://localhost:' + port + '/faye');


bayeux.attach(server);

bayeux.on('handshake', function(clientId) {
    console.log('Client connected', clientId);
});


client.connect();

emulator.onDisplay(function(digits, points) {
    var publication = client.publish('/display', {digits: digits, points: points});
    publication.then(function() {
        //console.log('Message received by server!');
    }, function(error) {
        console.log('There was a problem: ' + error.message);
    });
});

app.post("/key", (req, res, next) => {
    let code = req.query.code;
    emulator.keyPress(code);
    res.sendStatus(200);
});

app.post("/button", (req, res, next) => {
    let x = req.query.x;
    let y = req.query.y;
    emulator.buttonPress(x, y);
    res.sendStatus(200);
});

server.listen(port, function() {
    console.log('Listening on ' + port);
});

app.get('/', function(req, res) {
    res.sendFile(path.join(__dirname + '/index.html'));
});

