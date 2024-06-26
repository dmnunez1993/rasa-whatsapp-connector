from typing import List, Dict, Any

import requests

DEFAULT_WHATSAPP_API_TIMEOUT = 10


class RasaToWhatsappConverter:
    """
    Converter class that takes in rasa's collector outputs,
    converts them and sends them to the Whatsapp Cloud Api
    """
    def __init__(
        self,
        phone_identifier: str,
        token: str,
        graphql_api_version: str = 'v18.0',
        api_timeout: int = DEFAULT_WHATSAPP_API_TIMEOUT
    ):
        self._phone_identifier = phone_identifier
        self._token = token
        self._graphql_api_version = graphql_api_version
        self._api_timeout = api_timeout

    def _prepare_button_message(
        self,
        to: str,
        text: str,
        buttons: List[Dict[str, Any]],
    ):
        whatsapp_buttons = []

        # WhatsApp only allows up to three buttons per call
        for button in buttons[:3]:
            # Title can only have up to 20 characters.
            title = button['title'][0:20]
            whatsapp_id = button['payload']

            whatsapp_buttons.append(
                {
                    'type': 'reply',
                    'reply': {
                        'id': whatsapp_id,
                        'title': title
                    }
                }
            )

        message = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'interactive',
            'interactive':
                {
                    'type': 'button',
                    'body': {
                        "text": text
                    },
                    'action': {
                        'buttons': whatsapp_buttons
                    }
                }
        }

        return message

    def _prepare_list_message(
        self,
        to: str,
        text: str,
        buttons: List[Dict[str, Any]],
        list_name: str = "Select"
    ):
        whatsapp_list = []

        for button in buttons[:10]:
            # Title can only have up to 24 characters.
            title = button['title'][0:24]
            whatsapp_id = button['payload']

            whatsapp_list.append({
                'id': whatsapp_id,
                'title': title,
            })

        message = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'interactive',
            'interactive':
                {
                    'type': 'list',
                    'body': {
                        "text": text
                    },
                    'action':
                        {
                            'button':
                                list_name,
                            'sections':
                                [{
                                    'title': list_name,
                                    'rows': whatsapp_list,
                                }]
                        }
                }
        }

        return message

    def _prepare_text_message(self, to: str, text: str):
        message = {
            'messaging_product': 'whatsapp',
            'to': to,
            'text': {
                'body': text
            }
        }

        return message

    def prepare_message(
        self,
        to: str,
        text: str,
        buttons: List[Dict[str, Any]] | None = None,
    ):
        """
        Prepares a message compatible with Whatsapp Cloud Api
        Args:
            to (str): Message recipient.
            text (str): Message text.
            buttons (list or none): Optional list of buttons
        """
        if buttons is not None:
            if len(buttons) <= 3:
                message = self._prepare_button_message(to, text, buttons)
            else:
                message = self._prepare_list_message(to, text, buttons)
        else:
            message = self._prepare_text_message(to, text)

        return message

    def send_message(
        self,
        to: str,
        text: str,
        buttons: List[Dict[str, Any]] | None = None,
    ):
        """
        Sends a rasa message to Whatsapp Cloud Api
        Args:
            to (str): Message recipient.
            text (str): Message text.
            buttons (list or none): Optional list of buttons 
        """
        url = f"""
            https://graph.facebook.com/{self._graphql_api_version}{self._phone_identifier}/messages
        """.strip()
        headers = {'Authorization': f'Bearer {self._token}'}

        message = self.prepare_message(to, text, buttons)

        response = requests.post(
            url,
            headers=headers,
            json=message,
            timeout=self._api_timeout,
        )

        return response.json()

    def _get_value(self, data):
        if "entry" not in data or len(data["entry"]) == 0:
            raise ValueError("Provided data is invalid!")

        entry = data["entry"][0]

        if "changes" not in entry or len(entry["changes"]) == 0:
            raise ValueError("Provided data is invalid!")

        change = entry["changes"][0]

        if "value" not in change:
            raise ValueError("Provided data is invalid!")

        return change["value"]

    def get_message_from_whatsapp_hook(self, data):
        """
        Gets a rasa message from a whatsapp hook call
        Args:
            data(dict[str]): Whatsapp hook data.
        Returns:
            dict[str] or None: The message in the hook data or None.
        Raises:
            ValueError if the hook data is invalid
        """
        value = self._get_value(data)

        if "messages" not in value or len(value["messages"]) == 0:
            raise ValueError("Provided value is invalid")

        message = value["messages"][0]

        try:
            sender_id = message["from"]
            text = None

            if message["type"] == "text":
                text = message["text"]["body"]
            elif (
                message["type"] == "interactive"
                and message['interactive']['type'] == 'button_reply'
            ):
                text = message['interactive']['button_reply']['id']
            elif (
                message["type"] == "interactive"
                and message['interactive']['type'] == 'list_reply'
            ):
                text = message['interactive']['list_reply']['id']
        except KeyError as exc:
            raise ValueError("Provided data is invalid!") from exc

        if text is None:
            raise ValueError("Provided data is invalid!")

        return {"sender_id": sender_id, "text": text, "metadata": {}}
