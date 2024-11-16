from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, ValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
#from supabase import create_client, Client # incompatible with rasa
import random
import logging
import requests
import array

logging.getLogger(__name__)

cached_interview_questions = []

def get_interview_questions():
    global cached_interview_questions

    # aws lambda function to public dynamodb table
    data_url = "https://doitcs0az1.execute-api.eu-central-1.amazonaws.com/default/JCBGetAllQuestions"

    if cached_interview_questions:
        return cached_interview_questions

    response = requests.get(data_url)
    cached_interview_questions = response.json()
    return cached_interview_questions

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

        ids = [question["_id"] for question in selected_questions]
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
        selected_question = [question for question in interview_questions if question["_id"] == question_id][0]

        lowercase_first_letter = lambda s: s[:1].lower() + s[1:] if s else ''
        
        question_text = f"Here are some tips on how to answer the question: {selected_question['question']} \n"
        question_text += f"When answering this question {lowercase_first_letter(selected_question['good_answer_tips'])} \n"
        question_text += f"Try to orientate your answer around keywords like {', '.join(selected_question['good_answer_keywords'])} to make a good impression. \n"
        question_text += f"This is what a good answer could look like: {selected_question['good_answer_example']} \n"
        question_text += "Would you like detailed information about another question?"

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

        return [SlotSet("last_mock_question_id", str(selected_question["_id"])), SlotSet("mock_interview_answer", None)]
    
class ActionCheckMockAnswer(Action):

    def name(self) -> Text:
        return "action_check_mock_answer"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_response = tracker.get_slot("mock_interview_answer")

        questions = get_interview_questions()
        question_id = tracker.get_slot("last_mock_question_id")
        selected_question = [question for question in questions if question["_id"] == question_id][0]
        
        if any(keyword in user_response for keyword in selected_question["good_answer_keywords"]):
            dispatcher.utter_message(text="Great job! You used some of the right keywords in your response.")
        else:
            dispatcher.utter_message(text="Hmm, it seems like you missed some of the important keywords in your response. Try again!")
        
        return []


class ValidateAdditionalQuestionDetailsForm(FormValidationAction):
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

        if str(slot_value) in ["1", "2", "3", "4", "5"]:
            return {"question_detail_number": str(slot_value)}
        elif slot_value.lower() in ["1.", "2.", "3.", "4.", "5."]:
            return {"question_detail_number": str(["1.", "2.", "3.", "4.", "5."].index(slot_value.lower()) + 1)}
        elif slot_value.lower() in ["one", "two", "three", "four", "five"]:
            return {"question_detail_number": str(["one", "two", "three", "four", "five"].index(slot_value.lower()) + 1)}
        else:
            return {"question_detail_number": None}
        
class ValidateMockInterviewQuestionForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_mock_interview_question_form"

    def validate_mock_interview_answer(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate mock interview answer value."""

        if len(str(slot_value)) > 0:
            return {"mock_interview_answer": str(slot_value)}
        else:
            return {"mock_interview_answer": None}
        
class ValidatePredefinedSlots(ValidationAction):
    def validate_mock_interview_answer(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate mock_interview_answer value."""
        
        active_form = tracker.active_loop.get("name")

        if active_form == "mock_interview_question_form" and len(str(slot_value)) > 0:
            return {"mock_interview_answer": str(slot_value)}
        else:
            return {"mock_interview_answer": None}