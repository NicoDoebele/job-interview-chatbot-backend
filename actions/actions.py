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
from rasa_sdk.events import SlotSet, ActiveLoop
#from supabase import create_client, Client
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
import random
import logging

logging.getLogger(__name__)

def get_interview_questions():
    #public_url: str = "https://jyoivgbjcjpdkivdtlcb.supabase.co"
    #public_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5b2l2Z2JqY2pwZGtpdmR0bGNiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzExNDE0MjUsImV4cCI6MjA0NjcxNzQyNX0.U6F_dMw2brDiSeEIn9HvQshLpypr07Z082VpEamRKe0"
    #supabase: Client = create_client(public_url, public_key)

    #interview_question_response = supabase.table("interview_questions").select("*").execute()
    #interview_questions = interview_question_response["data"]

    #return interview_questions

    return [{"id": 1, "question": "Tell me about yourself."}, 
            {"id": 2, "question": "What are your strengths and weaknesses?"},
            {"id": 3, "question": "Why do you want to work here?"},
            {"id": 4, "question": "Where do you see yourself in 5 years?"},
            {"id": 5, "question": "What is your greatest achievement?"}]

class ActionProvideInterviewQuestions(Action):
    def name(self) -> Text:
        return "action_provide_interview_questions"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        NUM_QUESTIONS = 5
        interview_questions = get_interview_questions()
        selected_questions = random.sample(interview_questions, NUM_QUESTIONS)
        
        question_text = "Here are some interview questions to help you prepare: \n"
        for i, question in enumerate(selected_questions):
            question_text += f"{i+1}. {question['question']} \n"
        question_text += "Would you like more information on any of these questions?"

        dispatcher.utter_message(text=question_text)

        ids = [question["id"] for question in selected_questions]
        return [SlotSet("last_provided_question_ids", ids),]
    
class ActionExpandOnInterviewQuestion(Action):
    def name(self) -> Text:
        return "action_expand_on_interview_question"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        question_number = tracker.get_slot("question_detail_number")
        question_ids = tracker.get_slot("last_provided_question_ids")

        question_id = question_ids[int(question_number) - 1]

        interview_questions = get_interview_questions()
        selected_question = [question for question in interview_questions if question["id"] == question_id][0]
        
        question_text = f"Here is the question you wanted more information about: \n"
        question_text += f"{selected_question['question']} \n"
        question_text += "Would you like more information about another question?"

        dispatcher.utter_message(text=question_text)

        return [SlotSet("question_detail_number", None)]
    
class ActionAskMockInterviewQuestion(Action):
    def name(self) -> Text:
        return "action_ask_mock_interview_question"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        interview_questions = get_interview_questions()
        selected_question = random.sample(interview_questions, 1)[0]
        
        question_text = "Answer this interview question: \n"
        question_text += f"{selected_question['question']} \n"

        dispatcher.utter_message(text=question_text)

        return [SlotSet("last_mock_question_id", str(selected_question["id"]))] 

class ValidateAdditionQuestionDetailsForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_additional_question_details_form"

    def validate_question_detail_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate question detail number value."""

        logging.info(f"Slot value question detail number: {slot_value}")

        if str(slot_value) in ["1", "2", "3", "4", "5"]:
            # validation succeeded, set the value of the "cuisine" slot to value
            return {"question_detail_number": str(slot_value)}
        elif slot_value.lower() in ["one", "two", "three", "four", "five"]:
            return {"question_detail_number": str(["one", "two", "three", "four", "five"].index(slot_value.lower()) + 1)}
        else:
            # validation failed, set this slot to None so that the
            # user will be asked for the slot again
            return {"question_detail_number": None}