from python_bayeux import BayeuxClient
import requests


def main():
    client = BayeuxClient('http://localhost:8080/faye')
    client.subscribe('/display', display)
    while True:
        key = input()
        requests.post("http://localhost:8080/key?code="+key)


def display(message):
    text = ''
    digits = message['digits']
    points = message['points']
    for position in range(0, 12):
        text += digits[position]
        point = points[position]
        if point != ' ':
            text += point
    print(text)


if __name__ == "__main__":
    main()
