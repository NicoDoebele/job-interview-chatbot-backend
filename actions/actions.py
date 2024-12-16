from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, ValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop, AllSlotsReset, Restarted
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
#from supabase import create_client, Client # incompatible with rasa
import random
import logging
import requests
import array
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import os

logging.getLogger(__name__)

cached_interview_questions = []

# Get OLLAMA_HOST from environment variable, default to localhost
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')

def get_interview_questions():
    global cached_interview_questions

    # aws lambda function to public dynamodb table
    data_url = "https://doitcs0az1.execute-api.eu-central-1.amazonaws.com/default/JCBGetAllQuestions"

    if cached_interview_questions:
        return cached_interview_questions

    response = requests.get(data_url)
    cached_interview_questions = response.json()
    return cached_interview_questions

def get_random_coding_problem(difficulty: str = None, category: str = None, topic: str = None, include_paid: bool = False):
    """
    Fetch a random coding problem from LeetCode.
    :param difficulty: Optional filter for problem difficulty ('Easy', 'Medium', 'Hard')
    :param category: Optional filter for problem category ('algorithms', 'database', 'shell')
    :param topic: Optional filter for problem topic ('array', 'string', 'dynamic-programming', etc.)
    :param include_paid: Whether to include premium problems
    :return: Dictionary containing problem details or None if fetch fails
    """
    url = 'https://leetcode.com/graphql'
    
    query = '''
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
        problemsetQuestionList: questionList(
            categorySlug: $categorySlug
            limit: $limit
            skip: $skip
            filters: $filters
        ) {
            total: totalNum
            questions: data {
                acRate
                difficulty
                freqBar
                frontendQuestionId: questionFrontendId
                isFavor
                paidOnly: isPaidOnly
                status
                title
                titleSlug
                topicTags {
                    name
                    id
                    slug
                }
                hasSolution
                hasVideoSolution
            }
        }
    }
    '''
    
    variables = {
        'categorySlug': category.lower() if category else '',
        'limit': 100,
        'skip': 0,
        'filters': {
            'difficulty': difficulty.upper() if difficulty else None,
            'tags': [topic.lower()] if topic else None
        }
    }
    
    try:
        headers = {
            'Content-Type': 'application/json',
        }
        
        response = requests.post(url, 
                               json={'query': query, 'variables': variables},
                               headers=headers)
        
        response.raise_for_status()
        
        data = response.json()
        questions = data.get('data', {}).get('problemsetQuestionList', {}).get('questions', [])
        
        # Filter questions based on parameters
        filtered_questions = questions
        if not include_paid:
            filtered_questions = [q for q in filtered_questions if not q['paidOnly']]
        if topic:
            filtered_questions = [q for q in filtered_questions 
                                if any(tag['slug'] == topic.lower() for tag in q['topicTags'])]
        
        if filtered_questions:
            problem = random.choice(filtered_questions)
            return {
                'id': problem['frontendQuestionId'],
                'title': problem['title'],
                'link': f'https://leetcode.com/problems/{problem["titleSlug"]}/',
                'difficulty': problem['difficulty'],
                'topics': [tag['name'] for tag in problem['topicTags']],
                'has_solution': problem['hasSolution'],
                'acceptance_rate': f"{problem['acRate']:.1f}%"
            }
        else:
            print(f"No questions found matching the criteria: difficulty={difficulty}, category={category}, topic={topic}")
            return None
    
    except requests.RequestException as e:
        print(f"Error fetching problems: {e}")
        return None
    except KeyError as e:
        print(f"Unexpected response format: {e}")
        return None

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
        #selected_question = interview_questions[1]
        
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
        total_questions = tracker.get_slot("total_mock_questions") or 0
        successful_questions = tracker.get_slot("successful_mock_questions") or 0
        mock_history = tracker.get_slot("mock_interview_history") or []

        questions = get_interview_questions()
        question_id = tracker.get_slot("last_mock_question_id")
        selected_question = [question for question in questions if question["_id"] == question_id][0]
        
        # Store the Q&A in history
        mock_history.append({
            "question": selected_question["question"],
            "answer": user_response,
            "keywords": selected_question["good_answer_keywords"],
            "tips": selected_question["good_answer_tips"]
        })
        
        # Keep only last 10 Q&As
        if len(mock_history) > 10:
            mock_history = mock_history[-10:]

        text_to_classify = """{} \n\n {} \n\n {}""".format(
            "Please classify the user's answer to the following question. User should follow STAR principles and be thourough.",
            f"Question: '{selected_question['question']}'",
            f"User Answer: '{user_response}'",
            )
        
        classifications = ["outstanding answer", "good answer", "passable answer", "poor answer", "terrible answer"]

        classifer = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        classification = classifer(text_to_classify, candidate_labels=classifications)
        
        answer_successful = classification["labels"][0] in ["outstanding answer", "good answer", "passable answer"]
        confidence = classification["scores"][0]
        
        # Update counters
        total_questions += 1
        if answer_successful:
            successful_questions += 1
        
        # Calculate success ratio
        success_ratio = successful_questions / total_questions if total_questions > 0 else 0
        
        # Provide appropriate feedback based on ratio
        if answer_successful:
            if success_ratio > 0.8:
                feedback = "Excellent job! You're consistently giving strong answers. \n"
            elif success_ratio > 0.6:
                feedback = "Good work! You're showing solid improvement. \n"
            else:
                feedback = "Well done! Keep practicing to improve further. \n"
            feedback += f"Your answer was classified as: {classification['labels'][0]} with {confidence:.0%} confidence accross {len(classifications)} categories."
        else:
            if success_ratio < 0.3:
                feedback = "Sadly the answer was classified as suboptimal. Don't worry though, interview questions take practice. Here is an example of a good answer: \n"
            elif success_ratio < 0.5:
                feedback = "You're making progress, but this answer could be stronger. Here is an example of a good answer: \n"
            else:
                feedback = "This answer could be improved. Here is an example of a good answer: \n"
            feedback += f"{selected_question['good_answer_example']} \n"
            feedback += f"Your answer was classified as: {classification['labels'][0]} with {confidence:.0%} confidence accross {len(classifications)} categories."

        # Add performance stats if more than 3 questions attempted
        if total_questions >= 3:
            feedback += f"\nYour overall performance: {successful_questions}/{total_questions} questions answered effectively."
        
        dispatcher.utter_message(text=feedback)
        
        return [
            SlotSet("total_mock_questions", total_questions),
            SlotSet("successful_mock_questions", successful_questions),
            SlotSet("mock_interview_history", mock_history)
        ]


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

class ActionHandleMoreInfo(Action):
    def name(self) -> Text:
        return "action_handle_more_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the last intent before more_info request
        previous_intents = [event.get("parse_data", {}).get("intent", {}).get("name") for event in tracker.events if event.get("event") == "user"]
        if len(previous_intents) < 2:
            dispatcher.utter_message(response="utter_no_additional_info")
            return []

        last_intent = previous_intents[-2]  # -1 would be ask_more_info
        
        # Map intents to their expanded information
        more_info_responses = {
            "ask_star_method": "The STAR method can be broken down further:\n• Situation: Set the scene and context\n• Task: Describe the challenge and expectations\n• Action: Explain what you did and how\n• Result: Share the outcomes and what you learned\n\nExample:\nSituation: Customer complained about a faulty product\nTask: Needed to resolve issue and retain customer\nAction: Investigated problem, offered replacement, added bonus gift\nResult: Customer became a loyal advocate, shared positive review",
            
            "ask_salary_discussion": "Additional salary negotiation strategies:\n• Research industry standards on sites like Glassdoor\n• Consider the full package (benefits, bonuses, etc.)\n• Practice negotiation scenarios beforehand\n• Have a clear minimum acceptable offer\n• Be prepared to discuss performance metrics\n• Consider future growth opportunities",
            
            "ask_virtual_interview": "More virtual interview tips:\n• Have a backup device ready\n• Test your internet speed beforehand\n• Use ethernet instead of WiFi if possible\n• Practice looking at camera while speaking\n• Record yourself to check body language\n• Keep notes nearby but don't read from them\n• Have water and materials ready",
            
            "ask_what_to_wear": "Additional dress code considerations:\n• Check company social media for dress culture\n• Ensure clothes are pressed night before\n• Bring backup clothing items for emergencies\n• Consider the industry standards\n• Test your outfit by sitting/moving around\n• Choose comfortable but professional shoes",
            
            "ask_how_to_prepare": "Additional preparation tips:\n• Create an interview story bank\n• Research your interviewers on LinkedIn\n• Practice with industry-specific terminology\n• Prepare questions about company culture\n• Review company's competitors\n• Check recent company news and developments",
        }
        
        if last_intent in more_info_responses:
            dispatcher.utter_message(text=more_info_responses[last_intent])
        else:
            dispatcher.utter_message(response="utter_no_additional_info")
            
        return []

class ActionProvideCodingQuestion(Action):
    def name(self) -> Text:
        return "action_provide_coding_question"

    def extract_entities(self, tracker: Tracker) -> Dict[str, str]:
        """Extract entities from the message"""
        entities = {
            'difficulty': None,
            'topic': None,
            'category': None
        }
        
        # Get entities from the latest message
        message_entities = tracker.latest_message.get('entities', [])
        
        for entity in message_entities:
            if entity['entity'] == 'difficulty':
                entities['difficulty'] = entity['value']
            elif entity['entity'] == 'topic':
                entities['topic'] = entity['value']
            elif entity['entity'] == 'category':
                entities['category'] = entity['value']
        
        return entities

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Extract entities
        entities = self.extract_entities(tracker)
        
        # Use defaults if entities not found
        difficulty = entities['difficulty'] or None
        topic = entities['topic'] or None
        category = entities['category'] or 'algorithms'
        include_paid = False
        
        try:
            coding_question = get_random_coding_problem(
                difficulty=difficulty,
                category=category,
                topic=topic,
                include_paid=include_paid
            )
        except Exception as e:
            dispatcher.utter_message(text="I'm sorry, I couldn't fetch a coding question at the moment. Please try again later.")
            return []
        
        if coding_question is None:
            dispatcher.utter_message(text="I'm sorry, I couldn't find any questions matching your criteria. Try different filters.")
            return []

        question_text = f"Here is a coding question to practice: \n"
        question_text += f"Title: {coding_question['title']} \n"
        question_text += f"Difficulty: {coding_question['difficulty']} \n"
        question_text += f"Topics: {', '.join(coding_question['topics'])} \n"
        question_text += f"Acceptance Rate: {coding_question['acceptance_rate']} \n"
        question_text += f"Question ID: {coding_question['id']} \n"
        question_text += f"You can find the question on LeetCode: {coding_question['link']}"
        if coding_question['has_solution']:
            question_text += "\nThis question has an official solution available."

        dispatcher.utter_message(text=question_text)
        return []

class ActionMockInterviewSummary(Action):
    def name(self) -> Text:
        return "action_mock_interview_summary"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        total_questions = tracker.get_slot("total_mock_questions") or 0
        successful_questions = tracker.get_slot("successful_mock_questions") or 0
        
        if total_questions == 0:
            dispatcher.utter_message(text="You haven't attempted any mock interview questions yet. Would you like to try one?")
            return []
            
        success_ratio = successful_questions / total_questions
        
        summary_text = f"Mock Interview Summary:\n"
        summary_text += f"Questions: {total_questions} | Successful: {successful_questions} | Success Rate: {success_ratio:.0%}\n\n"
        
        if success_ratio > 0.8:
            summary_text += "Outstanding! Strong keywords, clear structure, professional delivery.\n"
            summary_text += "Next step: Try industry-specific scenarios."
        elif success_ratio > 0.6:
            summary_text += "Good progress! Clear concepts, growing confidence.\n"
            summary_text += "Focus on: More STAR examples, specific terminology."
        elif success_ratio > 0.4:
            summary_text += "On track. Areas to improve:\n"
            summary_text += "Keywords, STAR method, specific examples."
        else:
            summary_text += "Keep practicing!\n"
            summary_text += "Focus on: STAR method, keywords, common questions."

        summary_text += "\nUse 'get AI review' for detailed analysis."
        
        dispatcher.utter_message(text=summary_text)
        return []

class ActionGetGenAIReview(Action):
    def name(self) -> Text:
        return "action_get_genai_review"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        total_questions = tracker.get_slot("total_mock_questions") or 0
        mock_history = tracker.get_slot("mock_interview_history") or []
        
        if total_questions < 3:
            dispatcher.utter_message(text=f"Please answer at least 3 mock interview questions before requesting an AI review. You've answered {total_questions} so far.")
            return []

        if not mock_history:
            dispatcher.utter_message(text="No mock interview answers found to review.")
            return []

        prompt = """As an experienced interview coach, provide a thorough review of these interview responses.
        Be direct and honest but constructive. Focus on patterns across all answers.

        Interview Responses to Review:
        """
        
        for i, qa in enumerate(mock_history[-3:], 1):
            prompt += f"\nQuestion {i}: {qa['question']}\n"
            prompt += f"Response {i}: {qa['answer']}\n"

        prompt += """\nProvide a comprehensive review covering:
        1. Overall interview performance and communication style
        2. Effectiveness of STAR method usage
        3. Key strengths demonstrated across answers
        4. Main areas needing improvement
        5. Three specific, actionable recommendations for future interviews

        Keep the feedback constructive but direct. Keep yourself brief. Only reply in plain Text, do not use formatting. You are responding directly to the person who answered the questions."""

        try:
            # Make request to local Ollama instance
            response = requests.post(
                f'http://{OLLAMA_HOST}:11434/api/generate',
                json={
                    'model': 'llama3.2',
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'max_tokens': 750
                    }
                }
            )
            
            if response.status_code == 200:
                # Extract the generated text
                feedback = response.json().get('response', '').strip()
                
                # Format and send the feedback
                formatted_feedback = "Interview Performance Analysis:\n\n"
                formatted_feedback += feedback

                dispatcher.utter_message(text=formatted_feedback)
            else:
                raise Exception(f"Ollama request failed with status {response.status_code}")

        except Exception as e:
            print(f"Generation error: {e}")
            # Fallback to zero-shot classification
            classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
            
            feedback = "Interview Performance Review:\n\n"
            
            # Analyze overall communication style
            style_analysis = classifier(
                " ".join(qa['answer'] for qa in mock_history[-3:]),
                candidate_labels=["clear and structured", "somewhat organized", "needs more structure"],
                multi_label=False
            )
            
            # Analyze STAR method usage
            star_analysis = classifier(
                " ".join(qa['answer'] for qa in mock_history[-3:]),
                candidate_labels=["strong STAR usage", "partial STAR usage", "minimal STAR usage"],
                multi_label=False
            )
            
            feedback += f"Overall Style: {style_analysis['labels'][0]}\n"
            feedback += f"STAR Method: {star_analysis['labels'][0]}\n\n"
            
            feedback += "Key Observations:\n"
            if style_analysis['labels'][0] == "clear and structured":
                feedback += "• Your responses are well-structured and professional\n"
            elif style_analysis['labels'][0] == "somewhat organized":
                feedback += "• Your answers show good potential but need more consistent structure\n"
            else:
                feedback += "• Focus on organizing your responses more clearly\n"
                
            if star_analysis['labels'][0] == "strong STAR usage":
                feedback += "• Excellent use of the STAR method in your answers\n"
            elif star_analysis['labels'][0] == "partial STAR usage":
                feedback += "• Try to complete all STAR components in each answer\n"
            else:
                feedback += "• Practice incorporating the STAR method more consistently\n"

            feedback += "\nRecommendations:\n"
            feedback += "1. Start with clear situation descriptions\n"
            feedback += "2. Detail your specific actions\n"
            feedback += "3. Always highlight measurable results\n"
            feedback += "4. Practice structuring answers beforehand\n"

            feedback += "\nTHIS REVIEW WAS LIMITED DUE TO INCOMPLET CHATBOT SETUP"

            dispatcher.utter_message(text=feedback)

        return []

class ActionShowDressCode(Action):
    def name(self) -> Text:
        return "action_show_dress_code"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the dress code entity
        dress_code = next((e["value"] for e in tracker.latest_message["entities"] 
                          if e["entity"] == "dress_code"), None)
        
        if not dress_code:
            dispatcher.utter_message(text="I can help you with dress codes. Please specify which type: business casual, business formal, smart casual, professional, casual, or formal.")
            return []

        # Normalize the dress code value
        dress_code = dress_code.lower().replace(" ", "_")
        
        # Try to send the appropriate response
        response_name = f"utter_dress_code_{dress_code}"
        if response_name in domain.get("responses", {}):
            dispatcher.utter_message(response=response_name)
        else:
            dispatcher.utter_message(text="I'm not familiar with that dress code. I can help with business casual, business formal, smart casual, professional, casual, or formal attire.")
        
        return []

class ActionRestart(Action):
    def name(self) -> Text:
        return "action_restart"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Clear mock interview stats
        global cached_interview_questions
        cached_interview_questions = []
        
        # Get the active form if any
        active_form = tracker.active_loop.get('name')
        
        dispatcher.utter_message(text="Starting fresh! All previous data has been cleared.")
        
        events = [AllSlotsReset()]
        if active_form:
            events.append(ActiveLoop(None))
        events.append(Restarted())
        
        return events
