# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionAskMockInterviewQuestion(Action):
    def name(self) -> Text:
        return "action_ask_mock_interview_question"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the current question number from the slot
        question_number = tracker.get_slot("question_number") or 1

        # Dispatch appropriate question based on the current number
        if question_number == 1:
            dispatcher.utter_message(text="Let's start the mock interview! First question: Can you tell me about yourself?")
        elif question_number == 2:
            dispatcher.utter_message(text="Great! Next question: What are your strengths and weaknesses?")
        elif question_number == 3:
            dispatcher.utter_message(text="Now, how would you handle a challenging situation with a team member?")
        else:
            dispatcher.utter_message(text="That's all for now! Great job on the practice interview.")

        # Move to the next question for the next interaction
        return [SlotSet("question_number", question_number + 1)]


class ActionProvideFeedback(Action):
    def name(self) -> Text:
        return "action_provide_feedback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the current question number from the slot
        question_number = tracker.get_slot("question_number") or 1
        user_response = tracker.latest_message.get("text", "").lower()

        # Provide feedback based on the current question number
        if question_number == 1:
            if "experience" in user_response or "background" in user_response:
                dispatcher.utter_message(text="Nice job mentioning your experience! Including relevant background helps set the stage.")
            else:
                dispatcher.utter_message(text="Try to include a brief summary of your experience or background in your answer.")
        
        elif question_number == 2:
            if "strength" in user_response and "weakness" in user_response:
                dispatcher.utter_message(text="Good job covering both strengths and weaknesses!")
            else:
                dispatcher.utter_message(text="Remember to mention both a strength relevant to the job and a weakness you're working to improve.")

        elif question_number == 3:
            if "team member" in user_response or "communication" in user_response:
                dispatcher.utter_message(text="Great! Highlighting communication and teamwork is important.")
            else:
                dispatcher.utter_message(text="Try to emphasize communication and teamwork when discussing challenges with colleagues.")
        
        else:
            dispatcher.utter_message(text="Nice response! Keep practicing for confidence.")

        return []
