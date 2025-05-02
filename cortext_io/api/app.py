import os
import logging
import datetime
import subprocess
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi_mcp import FastApiMCP

app = FastAPI(title="Cortext IO API", description="API for Cortext IO text processing")

# File paths
input_file = "/home/ec2-user/cortext_io/cortext_io_input/input.txt"
java_script_path = "/home/ec2-user/cortext_io/AA_cortext_io_linux_0.1/AA_cortext_io_linux/AA_cortext_io_linux_run.sh"
scripts_dir = "/home/ec2-user/cortext_io/10K_RiskFactors_PROCESS/"
html_file_path = '/home/ec2-user/cortext_io/cortext_io_db/000_cortext_io.html'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ec2-user/cortext_io/api_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('cortext_api')

# Define Pydantic models for request and response data
class TextInput(BaseModel):
    text: str

class StatusResponse(BaseModel):
    status: str
    message: str

class ScriptResult(BaseModel):
    script: str
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float

class PythonScriptsResponse(BaseModel):
    status: str
    message: str
    run_id: str
    results: List[ScriptResult]

class JavaResponse(BaseModel):
    status: str
    message: str
    output: Optional[str] = None
    error: Optional[str] = None

class ErrorResponse(BaseModel):
    status: str
    message: str
    run_id: Optional[str] = None

@app.post("/write", response_model=StatusResponse)
async def write_to_file(data: TextInput):
    """
    Write the provided text to the input file.
    """
    try:
        with open(input_file, 'w') as file:
            file.write(data.text)
        return StatusResponse(status="success", message="Text written to file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-html")
async def download_html():
    """
    Download the generated HTML file.
    """
    try:
        # Check if the file exists
        if not os.path.exists(html_file_path):
            raise HTTPException(
                status_code=404, 
                detail="HTML file not found"
            )

        # Return the file as an attachment
        return FileResponse(
            path=html_file_path,
            media_type='text/html',
            filename='000_cortext_io.html'
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-java", response_model=JavaResponse)
async def run_java():
    """
    Run the Java script and return the results.
    """
    try:
        # Change to the required directory
        os.chdir(scripts_dir)
        
        # Run the Java script
        process = subprocess.Popen(
            [java_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Get the output and error
        stdout, stderr = process.communicate()
        
        # Check if the process completed successfully
        if process.returncode == 0:
            return JavaResponse(
                status="success",
                message="Java process executed successfully",
                output=stdout.decode('utf-8')
            )
        else:
            return JavaResponse(
                status="error",
                message="Java process failed",
                error=stderr.decode('utf-8')
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-python-scripts", response_model=PythonScriptsResponse)
async def run_python_scripts():
    """
    Run all Python scripts in sequence and return the results.
    """
    # Generate a unique run ID for tracking this execution
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        logger.info(f"[{run_id}] Starting Python scripts execution")
        
        # Change to the scripts directory
        os.chdir(scripts_dir)
        logger.info(f"[{run_id}] Changed directory to: {scripts_dir}")
        
        scripts = [
            "python3 CORTEXT_TRANSFORM.py",
            "python3 CORTEXT_LAYOUT_10K.py 40",
            "python3 AssociateWeb_10K.py",
            "python3 StraightShooterIndex.py"
        ]
        
        results = []
        
        # Run each script in sequence
        for i, script in enumerate(scripts):
            logger.info(f"[{run_id}] Running script {i+1}/{len(scripts)}: {script}")
            start_time = datetime.datetime.now()
            
            process = subprocess.Popen(
                script,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate()
            
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            
            # Log the results
            if process.returncode == 0:
                logger.info(f"[{run_id}] Script {script} completed successfully in {duration:.2f} seconds")
                if stdout_str:
                    logger.info(f"[{run_id}] Output: {stdout_str[:200]}{'...' if len(stdout_str) > 200 else ''}")
            else:
                logger.error(f"[{run_id}] Script {script} failed with return code {process.returncode} in {duration:.2f} seconds")
                if stderr_str:
                    logger.error(f"[{run_id}] Error: {stderr_str}")
                if stdout_str:
                    logger.info(f"[{run_id}] Output: {stdout_str[:200]}{'...' if len(stdout_str) > 200 else ''}")
            
            results.append(ScriptResult(
                script=script,
                returncode=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration
            ))
            
            # If any script fails, stop the sequence
            if process.returncode != 0:
                logger.error(f"[{run_id}] Stopping script sequence due to failure")
                return PythonScriptsResponse(
                    status="error",
                    message=f'Script {script} failed',
                    run_id=run_id,
                    results=results
                )
        
        logger.info(f"[{run_id}] All Python scripts executed successfully")
        return PythonScriptsResponse(
            status="success",
            message="All Python scripts executed successfully",
            run_id=run_id,
            results=results
        )
        
    except Exception as e:
        logger.exception(f"[{run_id}] Exception occurred: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "status": "error",
                "message": str(e),
                "run_id": run_id
            }
        )

@app.post("/run-full-process", response_model=PythonScriptsResponse)
async def run_full_process():
    """
    Run the complete process: Java script followed by all Python scripts.
    """
    try:
        # First run the Java process
        java_result = await run_java()
        
        # If Java process failed, return the error
        if java_result.status == "error":
            run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            return PythonScriptsResponse(
                status="error",
                message=f"Java process failed: {java_result.error}",
                run_id=run_id,
                results=[]
            )
        
        # Then run the Python scripts
        return await run_python_scripts()
        
    except Exception as e:
        run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.exception(f"[{run_id}] Exception in full process: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "status": "error",
                "message": str(e),
                "run_id": run_id
            }
        )

# Add MCP integration
mcp = FastApiMCP(
    app, 
    name="Cortext IO API",
    description="API for Cortext IO text processing"
)
# Mount the MCP server to your FastAPI app
mcp.mount()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)