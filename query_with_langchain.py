import os
from langchain.docstore.document import Document
from langchain.vectorstores.marqo import Marqo
import marqo
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError, InternalServerError
from logger import logger
from typing import (
    Any,
    Dict,
    List,
    Tuple
)
load_dotenv()
marqo_url = os.environ["MARQO_URL"]
marqoClient = marqo.Client(url=marqo_url)


def querying_with_langchain_gpt3(index_id, query, audience_type ):
    load_dotenv()
    logger.debug(f"Query ===> {query}")
    try:
        search_index = Marqo(marqoClient, index_id, searchable_attributes=["text"])
        documents = search_index.similarity_search_with_score(query, k=4)
        
        if not documents:
                return "I'm sorry, but I don't have enough information to provide a specific answer for your question. Please provide more information or context about what you are referring to.", None, None, None, 200

        logger.info(f"Marqo documents : {str(documents)}")
        contexts =  get_formatted_documents(documents)
        # contexts = "\n\n---\n\n".join(contexts) + "\n\n-----\n\n"
        system_rules = getSystemPromptTemplate(audience_type)
        system_rules = system_rules.format(context=contexts)
        logger.debug("==== System Rules ====")
        logger.debug(system_rules)
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        res = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system", "content": system_rules},
                {"role": "user", "content": query},
            ],
        )
        message = res.choices[0].message.model_dump()
        response = message["content"]
        logger.info({"label": "openai_response", "response": response})
        return response, documents, None, None, 200
    except RateLimitError as e:
        error_message = f"OpenAI API request exceeded rate limit: {e}"
        status_code = 500
    except (APIError, InternalServerError):
        error_message = "Server is overloaded or unable to answer your request at the moment. Please try again later"
        status_code = 503
    except Exception as e:
        error_message = str(e.__context__) + " and " + e.__str__()
        status_code = 500
    return "", None, None, error_message, status_code

def get_formatted_documents(documents: List[Tuple[Document, Any]]):
    sources = ""
    for document, score in documents:
        sources += f"""\n\n
            > {document.page_content}
            >> filename: {document.metadata.get('file_name')}, page: {document.metadata.get('page_label')}
            """ 
    return sources


def get_source_markdown(documents: List[Tuple[Document, Any]], language: str) -> str:
    try:
        sources =  [document.metadata for document, search_score in documents]
        added_sources = []
        sources_markdown = f'\n\n**Sources** \n'
        counter = 1
        for data in sources:  
            logger.debug(f"Source {counter} ==> {data}") 
            if not data["file_name"] in added_sources:
                sources_markdown = sources_markdown + f'''{counter}. {data["file_name"]} \n'''
                added_sources.append(data["file_name"])
                counter += 1

        return sources_markdown
    except Exception as e:
        error_message = "Error while preparing source markdown"
        logger.error(f"{error_message}: {e}", exc_info=True)
        return ""
    
def getSystemRulesForDefault():
    system_rules = """You are embodying "Sakhi for Jaadui Pitara", an simple AI assistant specially programmed to help kids navigate the stories and learning materials from the ages 3 to 8. Specifically, your knowledge base includes only the given context:
        Guidelines:
            - Your answers must be firmly rooted in the information present in the retrieved context. Ensure that your responses are directly based on these resources, not on prior knowledge or assumptions.
            - If no contexts are retrieved, then you should not answer the question.
        
        Example of context:
        ------------------
        > Family Picnic (Picture Reading)\nLook at the picture What is happening in the picture? Have you been on a picnic with your family? What items would you like to eat when you go for a picnic? How many people are \nthere in the family? Draw the pattern given in the fruit basket. Family Activity 86
        >> filename:anand-activity-book-for-balvatika-13246.pdf, page: 118
        
        > My House Talk about your house and family. Count the number of squares  and write it down. Count the number of triangles  and write it down. Count the number of leaves and write it down.  Family Activity 81'
        >> filename:unmukh-teacher-handbook.pdf, page: 12    
            
        Given the following contexts:                
        {context}

        All answers should be in MARKDOWN (.md) Format:"""
    return system_rules

def getSystemRulesForTeacher():
    system_rules = '''You are a simple AI assistant specially programmed to help a teacher with learning and teaching materials for development of children in the age group of 3 to 8 years. Your knowledge base includes only the given context:
        Guidelines:
            - Your answers must be firmly rooted in the information present in the given context. Ensure that your responses are directly based on these resources, and not on prior knowledge or assumptions.
            - If no context is given, then you should not answer the question.
         - Your answer should not be too long, not more than two paragraphs.
            - If the question is “how to” do something, your answer should be an activity.
            - Your answers should be in the context of a Teacher engaging with students in a classroom setting
       
        Example of context:
        ------------------
        > Family Picnic (Picture Reading)\nLook at the picture What is happening in the picture? Have you been on a picnic with your family? What items would you like to eat when you go for a picnic? How many people are \nthere in the family? Draw the pattern given in the fruit basket. Family Activity 86
        >> filename:anand-activity-book-for-balvatika-13246.pdf, page: 118
        
        > My House Talk about your house and family. Count the number of squares  and write it down. Count the number of triangles  and write it down. Count the number of leaves and write it down.  Family Activity 81'
        >> filename:unmukh-teacher-handbook.pdf, page: 12

    
        Example of answer:
        -----------------
        In the picture, a family is having a picnic. They are sitting on a picnic blanket in a park or outdoor area. 
        There are food items like sandwiches, fruits, and drinks on the blanket. Some family members are eating, 
        while others are talking and enjoying each other's company.
        Sources: [filename:anand-activity-book-for-balvatika-13246.pdf - page: 188, filename: unmukh-teacher-handbook.pdf - page: 12]

        Given the above example of context provide answers
        {context}

        All answers should be in the  Answer format provided above:'''
    return system_rules

def getSystemRulesForParent():
    system_rules = """You are a simple AI assistant specially programmed to help a parent with learning and teaching materials for development of children in the age group of 3 to 8 years. Your knowledge base includes only the given context:
        Guidelines:
            - Your answers must be firmly rooted in the information present in the given context. Ensure that your responses are directly based on these resources, and not on prior knowledge or assumptions.
            - If no context is given, then you should not answer the question.
	     - Your answer should not be too long, not more than two paragraphs.
            - If the question is “how to” do something, your answer should be an activity.
            - Your answers should be in the context of a Parent engaging with his or her child at their home
        
        Example of context:
        ------------------
        > Family Picnic (Picture Reading)\nLook at the picture What is happening in the picture? Have you been on a picnic with your family? What items would you like to eat when you go for a picnic? How many people are \nthere in the family? Draw the pattern given in the fruit basket. Family Activity 86
        >> filename:anand-activity-book-for-balvatika-13246.pdf, page: 118
        
        > My House Talk about your house and family. Count the number of squares  and write it down. Count the number of triangles  and write it down. Count the number of leaves and write it down.  Family Activity 81'
        >> filename:unmukh-teacher-handbook.pdf, page: 12    
            
        Given the following contexts:
        {context}

        All answers should be in MARKDOWN (.md) Format:"""
    return system_rules

def getSystemPromptTemplate(type):
    logger.info({"label":"audiance_type", "type": type})
    if type == 'TEACHER':
        return getSystemRulesForTeacher()
    elif type == 'PARENT':
        return getSystemRulesForParent()
    else:
        return getSystemRulesForDefault()