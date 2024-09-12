from websockets.sync.client import connect
import json


def main():
    with connect("ws://localhost:8766") as websocket:
        print("Connected to server.")
        id = 0
        while True:
            cmd = input("Enter to communicate with server. Type 'exit' to exit: ")
            if cmd == "exit":
                print("Exiting...")
                break
            req_json = {
                'id': id,
                'instruction': 'get_all_players_data'
            }
            id += 1
            req = json.dumps(req_json)
            print("The request string is: " + req)
            print("Sending request to server...")
            websocket.send(req)
            print("Waiting for response...")
            while True:
                try:
                    response = websocket.recv(0.5)
                    print("Received response from server: " + response)
                except TimeoutError:
                    print("Receiving finished.")
                    break


if __name__ == "__main__":
    main()