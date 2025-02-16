from pydantic import BaseModel
from typing import Callable
import base64
from PIL import Image

from roboai.agent import Agent
from roboai.task import Task

from shared.utils.robosim_client import get_objects_on_table, pick, place, get_image, get_grasp_image
from shared.utils.model_server_client import answer_question_from_image
import shared.utils.gradio_client as gradio
import shared.utils.replicate_client as replicate

import logging

log = logging.getLogger("roboai")
log.setLevel(logging.DEBUG)

class Tool(BaseModel):
    name: str
    func: Callable
    description: str
    example: str

def extract_code(raw_input, language="python"):
    start_delimiter = f"```{language}"
    if start_delimiter not in raw_input:
        start_delimiter = "```"

    code_start_index = raw_input.find(start_delimiter)
    if code_start_index == -1:
        code_start_index = 0
    else:
        code_start_index += len(start_delimiter)

    end_delimiter = "```"
    code_end_index = raw_input.find(end_delimiter, code_start_index)
    if code_end_index == -1:
        code_end_index = len(raw_input)

    code = raw_input[code_start_index:code_end_index].strip()
    log.debug(f"Extracted code: \n{code}")
    return code


class RobotJob:
    def __init__(self):
        pass

    def run(self):
        '''
        Job to:
            1. Understand the scene
            2. Create a plan to clear the table
        '''        

        im = get_image()
        prompt = "Concisely describe the objects on the table."

        task_scene = Task(
            f"Given the following image, describe the objects on the table."
        )
        task_scene.add_task_image(im)
        scene_agent = Agent(
            name="Scene",
            model="ollama/llava:latest",
            system_message="""
            You are an agent that describes the scene. Focus on the objects on the table.
            """
        )
        task_scene.add_solving_agent(scene_agent)
        output = task_scene.run()
        # output = gradio.moondream_answer_question_from_image(im, prompt)
        # output = replicate.moondream_answer_question_from_image(im, prompt)
        # if "result" not in output.keys():
        #     log.error("No result found.")
        #     return
        
        # output = output["result"]

        task = Task(
            f"Given the following summary, return just a list in python of the objects on the table. The table is not an object. Summary: \n{output}",
            expected_output_format="""
                objects_on_table = ["Object 1", "Object 2", "Object 3"]
            """
            )
        analyzer_agent = Agent(
            name="Analyzer",
            model="openrouter/huggingfaceh4/zephyr-7b-beta:free",
            system_message="""
            You are a helpful agent that concisely responds with only code.
            Use only the provided functions, do not add any extra code.
            """
        )
        task.add_solving_agent(analyzer_agent)
        output = task.run()
        # output = '```objects_on_table = ["Box of Cereal", "Carton of Milk", "Can of Soup"]```'
        code = extract_code(output)
        exec_vars = {}
        exec(code, exec_vars)
        log.info(exec_vars.get("objects_on_table", None))
        list_of_objects = exec_vars.get("objects_on_table", None)

        plan_task = Task(
            f"""Create a plan for a robot to remove the following objects from the table:
                {list_of_objects}
                Do not add any extra steps.
            """,
            # expected_output_format="""
            #     1. pick object1
            #     2. place object1
            #     3. pick object2
            #     4. place object2
            #     5. pick object3
            #     6. place object3
            # """
            expected_output_format="A numbered list of steps constrained to the provided functions."
        )
        plan_task.register_tool(
            name="pick",
            func=pick,
            description="Robot picks up the provided arg 'object_name'",
            example='"pick_success = pick(object_name="Object 1")" --> Returns: True '
        )

        plan_task.register_tool(
            name="place",
            func=place,
            description="Robot places the provided arg 'object_name'",
            example='"place_success = place(object_name="Object 1")" --> Returns: True '
        )

        planner_agent = Agent(
            name="Planner",
            model="openrouter/huggingfaceh4/zephyr-7b-beta:free",
            system_message=f"""
            You are a planner that breaks down tasks into steps for robots.
            Create a conscise set of steps that a robot can do.
            Do not add any extra steps.
            """ + plan_task.generate_tool_prompt()
        )

        plan_task.add_solving_agent(planner_agent)
        # log.info(plan_task)
        output = plan_task.run()
        log.info(output)


        plan_generated = True
        code = extract_code(output)
        exec_vars = plan_task.get_exec_vars()
        try:
            exec(code, exec_vars)
        except Exception as e:
            log.error(f"Error executing plan: {e}")
            plan_generated = False

        # Validate the plan?

        # Execute the plan
        if not plan_generated:
            coder_task = Task(
                f"""Return python code to execute the plan using only the provided functions.
                    {output}
                """
                )
            coder_task.register_tool(
                name="pick",
                func=pick,
                description="Robot picks up the provided arg 'object_name'",
                example='"pick_success = pick(object_name="Object 1")" --> Returns: True '
            )
            coder_task.register_tool(
                name="place",
                func=place,
                description="Robot places the provided arg 'object_name'",
                example='"place_success = place(object_name="Object 1")" --> Returns: True '
            )
            coder_agent = Agent(
                name="Coder",
                # model="ollama/gemma:7b",
                model="openrouter/huggingfaceh4/zephyr-7b-beta:free",
                system_message="""
                You are a coder that writes concise and exact code to execute the plan.
                Use only the provided functions.
                """ + coder_task.generate_tool_prompt()
            )
            coder_task.add_solving_agent(coder_agent)
            log.info(coder_task)
            output = coder_task.run()

            code = extract_code(output)
            exec_vars = coder_task.get_exec_vars()
            exec(code, exec_vars)


if __name__ == "__main__":
    # job = RobotJob()
    # job.run()
    
    # test vqa

    # output = gradio.qwen_vl_max_answer_question_from_image(Image.open("shared/data/tmp.png"), "What is the color of the table?")
    import shared.utils.huggingface_client as hf

    output = hf.vila_query("What is the color of the table?")
   
    print(output)