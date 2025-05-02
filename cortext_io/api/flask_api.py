import os
import logging
import datetime
import subprocess
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

input_file = "/home/ec2-user/cortext_io/cortext_io_input/input.txt"
java_script_path = "/home/ec2-user/cortext_io/AA_cortext_io_linux_0.1/AA_cortext_io_linux/AA_cortext_io_linux_run.sh"
scripts_dir = "/home/ec2-user/cortext_io/10K_RiskFactors_PROCESS/"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ec2-user/cortext_io/api_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('cortext_api')

@app.route('/write', methods=['POST'])
def write_to_file():
    data = request.json

    if not data or 'text' not in data:
        return jsonify({'status': 'error', 'message': 'No text provided'}), 400

    text = data['text']

    try:
        with open(input_file, 'w') as file:
            file.write(text)
        return jsonify({'status': 'success', 'message': 'Text written to file'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download-html', methods=['GET'])
def download_html():
    html_file_path = '/home/ec2-user/cortext_io/cortext_io_db/000_cortext_io.html'

    try:
        # Check if the file exists
        if not os.path.exists(html_file_path):
            return jsonify({
                'status': 'error',
                'message': 'HTML file not found'
            }), 404

        # Return the file as an attachment
        return send_file(
            html_file_path,
            mimetype='text/html',
            as_attachment=True,
            download_name='000_cortext_io.html'
        )

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/run-java', methods=['POST'])
def run_java():
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
            return jsonify({
                'status': 'success',
                'message': 'Java process executed successfully',
                'output': stdout.decode('utf-8')
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Java process failed',
                'error': stderr.decode('utf-8')
            }), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/run-python-scripts', methods=['POST'])
def run_python_scripts():
    try:
        # Generate a unique run ID for tracking this execution
        run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
            
            results.append({
                'script': script,
                'returncode': process.returncode,
                'stdout': stdout_str,
                'stderr': stderr_str,
                'duration_seconds': duration
            })
            
            # If any script fails, stop the sequence
            if process.returncode != 0:
                logger.error(f"[{run_id}] Stopping script sequence due to failure")
                return jsonify({
                    'status': 'error',
                    'message': f'Script {script} failed',
                    'run_id': run_id,
                    'results': results
                }), 500
        
        logger.info(f"[{run_id}] All Python scripts executed successfully")
        return jsonify({
            'status': 'success',
            'message': 'All Python scripts executed successfully',
            'run_id': run_id,
            'results': results
        }), 200
        
    except Exception as e:
        logger.exception(f"[{run_id if 'run_id' in locals() else 'UNKNOWN'}] Exception occurred: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'run_id': run_id if 'run_id' in locals() else 'UNKNOWN'
        }), 500

@app.route('/run-full-process', methods=['POST'])
def run_full_process():
    """Run the complete process: Java script followed by all Python scripts"""
    try:
        # First run the Java process
        java_result = run_java()
        
        # If Java process failed, return the error
        if java_result[1] != 200:
            return java_result
        
        # Then run the Python scripts
        return run_python_scripts()
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
