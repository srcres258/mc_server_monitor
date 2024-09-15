const ws = new WebSocket('ws://localhost:8765');
let id = 0;

ws.onopen = function() {
    console.log('Connected to server');
    setTimeout(sendMessage, 1000);
};

ws.onmessage = function(event) {
    console.log('Received message from server: ' + event.data);
};

ws.onclose = function() {
    console.log('Connection closed');
};

ws.onerror = function(error) {
    console.log('Error occurred: ' + error.message);
};

function sendMessage() {
    const msg_json = {
        "id": id,
        "instruction": "get_all_players_data"
    };
    id += 1;
    const msg_str = JSON.stringify(msg_json);
    console.log('Sending message to server: ' + msg_str);
    ws.send(msg_str);
    setTimeout(sendMessage, 1000);
}
