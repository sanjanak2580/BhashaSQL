#!/usr/bin/env python3
"""
BhashaQL - A Hinglish SQL Compiler
Flask Web Interface Backend
"""

import sys
import os
import json
from typing import Dict, Any, List

from waitress import serve
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

# Add compiler to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'compiler'))

from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from compiler.optimizer import QueryOptimizer
from compiler.codegen import CodeGenerator
from compiler.errors import ErrorCollector, CompilerError
from runtime.executor import QueryExecutor

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global compiler instance
compiler = None

def get_compiler():
    """Get or create compiler instance"""
    global compiler
    if compiler is None:
        compiler = WebBhashaQLCompiler("runtime/database.db")
    return compiler

class WebBhashaQLCompiler:
    """Web-friendly BhashaQL compiler that returns structured data"""
    
    def __init__(self, db_path: str = "runtime/database.db"):
        self.db_path = db_path
        self.executor = QueryExecutor(db_path)
        self.error_collector = ErrorCollector()
        self.verbose = False
        self.show_sql = False
        self.show_ir = False
        self.show_ast = False
    
    def compile_and_execute_web(self, source: str) -> Dict[str, Any]:
        """Compile and execute BhashaQL source code, returning structured results"""
        result = {
            "success": False,
            "errors": [],
            "warnings": [],
            "results": [],
            "sql_statements": [],
            "ast": None,
            "ir": None,
            "execution_time": 0,
            "affected_rows": 0,
            "message": ""
        }
        
        try:
            # Initialize executor
            init_result = self.executor.initialize()
            if not init_result.success:
                result["errors"].append(f"Database initialization error: {init_result.message}")
                return result
            
            # Phase 1: Lexical Analysis
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            
            # Phase 2: Parsing
            parser = Parser(tokens)
            try:
                ast = parser.parse()
                if self.show_ast:
                    result["ast"] = str(ast)
            except CompilerError as e:
                self.error_collector.add_error(e)
                result["errors"].append(f"Parse Error: {e}")
                return result
            
            # Phase 3: Semantic Analysis
            semantic_analyzer = SemanticAnalyzer()
            try:
                semantic_valid = semantic_analyzer.analyze(ast)
                
                if not semantic_valid:
                    errors = semantic_analyzer.get_errors()
                    for error in errors:
                        self.error_collector.add_error(error)
                        result["errors"].append(str(error))
                    
                    warnings = semantic_analyzer.get_warnings()
                    for warning in warnings:
                        result["warnings"].append(str(warning))
                    
                    return result
                
            except Exception as e:
                result["errors"].append(f"Semantic analysis failed: {e}")
                return result
            
            # Phase 4: Intermediate Representation Generation
            codegen = CodeGenerator(semantic_analyzer.symbol_table)
            try:
                ir_program = codegen.ir_generator.generate(ast)
                if self.show_ir:
                    result["ir"] = str(ir_program)
                
            except Exception as e:
                result["errors"].append(f"IR generation failed: {e}")
                return result
            
            # Phase 5: Optimization
            optimizer = QueryOptimizer()
            try:
                optimized_ir = optimizer.optimize(ir_program)
                
            except Exception as e:
                result["errors"].append(f"Optimization failed: {e}")
                return result
            
            # Phase 6: Code Generation
            try:
                sql_statements = codegen.generate_sql(ast)
                result["sql_statements"] = sql_statements
                
            except Exception as e:
                result["errors"].append(f"Code generation failed: {e}")
                return result
            
            # Phase 7: Execution
            try:
                results = self.executor.execute_sql_batch(sql_statements)
                
                total_time = 0
                total_affected = 0
                all_success = True
                
                for query_result in results:
                    if query_result.success:
                        if query_result.data:
                            # Convert query result to web-friendly format
                            result_data = {
                                "columns": query_result.columns,
                                "data": query_result.data,
                                "row_count": len(query_result.data),
                                "execution_time": query_result.execution_time,
                                "message": query_result.message
                            }
                            result["results"].append(result_data)
                        else:
                            result["results"].append({
                                "message": query_result.message,
                                "affected_rows": query_result.affected_rows,
                                "execution_time": query_result.execution_time,
                                "success": True
                            })
                        
                        total_time += query_result.execution_time
                        total_affected += query_result.affected_rows
                    else:
                        result["errors"].append(f"Execution Error: {query_result.message}")
                        all_success = False
                
                result["success"] = all_success
                result["execution_time"] = total_time
                result["affected_rows"] = total_affected
                
                if all_success and len(result["errors"]) == 0:
                    result["message"] = f"Successfully executed {len(results)} query(s)"
                
            except Exception as e:
                result["errors"].append(f"Execution failed: {e}")
                return result
            
        except Exception as e:
            result["errors"].append(f"Unexpected error: {e}")
            return result
        finally:
            # Don't shutdown - keep connection persistent for web app
            pass
        
        return result

# Create web compiler instance
web_compiler = WebBhashaQLCompiler()

# HTML Template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BhashaQL - Hinglish SQL Compiler</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            padding: 30px;
        }
        
        .input-section, .output-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
        }
        
        .section-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 15px;
            color: #333;
        }
        
        .query-input {
            width: 100%;
            min-height: 200px;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: vertical;
            transition: border-color 0.3s;
        }
        
        .query-input:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
        }
        
        .btn-example {
            background: #28a745;
            color: white;
        }
        
        .btn-example:hover {
            background: #218838;
        }
        
        .output-area {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            min-height: 200px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            white-space: pre-wrap;
        }
        
        .success {
            color: #28a745;
            font-weight: 600;
        }
        
        .error {
            color: #dc3545;
            font-weight: 600;
        }
        
        .warning {
            color: #ffc107;
            font-weight: 600;
        }
        
        .result-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .result-table th,
        .result-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        
        .result-table th {
            background-color: #f2f2f2;
            font-weight: 600;
        }
        
        .examples {
            margin-top: 20px;
            padding: 15px;
            background: #e9ecef;
            border-radius: 8px;
        }
        
        .examples h3 {
            margin-bottom: 10px;
            color: #333;
        }
        
        .example-item {
            background: white;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        
        .example-item:hover {
            background: #f8f9fa;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 15px;
        }
        
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.3s;
        }
        
        .tab.active {
            border-bottom-color: #4facfe;
            color: #4facfe;
            font-weight: 600;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }
        
        .stat-value {
            font-size: 1.5em;
            font-weight: 700;
            color: #4facfe;
        }
        
        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            header h1 {
                font-size: 2em;
            }
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4facfe;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 BhashaQL</h1>
            <p>Hinglish SQL Compiler - Write SQL in Hinglish!</p>
        </header>
        
        <div class="main-content">
            <div class="input-section">
                <h2 class="section-title">📝 Enter BhashaQL Query</h2>
                <textarea id="queryInput" class="query-input" placeholder="Type your BhashaQL query here...

Examples:
• banaye table students (id number, name text, age number);
• laye * se students jahan age > 18;
• daalen mein students values (1, 'Aman', 20);"></textarea>
                
                <div class="button-group">
                    <button onclick="executeQuery()" class="btn-primary">🔥 Execute Query</button>
                    <button onclick="clearInput()" class="btn-secondary">🗑️ Clear</button>
                    <button onclick="showExamples()" class="btn-example">💡 Examples</button>
                </div>
                
                <div class="examples" id="examples" style="display: none;">
                    <h3>📚 Example Queries:</h3>
                    <div class="example-item" onclick="setExample('banaye table employees (id number, name text, department text, salary number);')">
                        banaye table employees (id number, name text, department text, salary number);
                    </div>
                    <div class="example-item" onclick="setExample('daalen mein employees values (1, \"Rahul\", \"IT\", 50000);')">
                        daalen mein employees values (1, "Rahul", "IT", 50000);
                    </div>
                    <div class="example-item" onclick="setExample('laye * se employees jahan salary > 40000;')">
                        laye * se employees jahan salary > 40000;
                    </div>
                    <div class="example-item" onclick="setExample('badlein employees set karein salary = 60000 jahan department = \"IT\";')">
                        badlein employees set karein salary = 60000 jahan department = "IT";
                    </div>
                    <div class="example-item" onclick="setExample('mitayein se employees jahan salary < 30000;')">
                        mitayein se employees jahan salary < 30000;
                    </div>
                    <div class="example-item" onclick="setExample('laye count(*) se employees;')">
                        laye count(*) se employees;
                    </div>
                </div>
            </div>
            
            <div class="output-section">
                <h2 class="section-title">📊 Results</h2>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>Executing query...</p>
                </div>
                
                <div class="tabs">
                    <div class="tab active" onclick="showTab('results')">Results</div>
                    <div class="tab" onclick="showTab('sql')">SQL</div>
                    <div class="tab" onclick="showTab('stats')">Statistics</div>
                </div>
                
                <div id="resultsTab" class="tab-content active">
                    <div id="output" class="output-area">Results will appear here...</div>
                </div>
                
                <div id="sqlTab" class="tab-content">
                    <div id="sqlOutput" class="output-area">Generated SQL will appear here...</div>
                </div>
                
                <div id="statsTab" class="tab-content">
                    <div id="statsOutput" class="stats">
                        <div class="stat-card">
                            <div class="stat-value" id="queryCount">0</div>
                            <div class="stat-label">Queries Executed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="executionTime">0s</div>
                            <div class="stat-label">Execution Time</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="affectedRows">0</div>
                            <div class="stat-label">Affected Rows</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let queryCount = 0;
        
        function executeQuery() {
            const query = document.getElementById('queryInput').value.trim();
            if (!query) {
                alert('Please enter a BhashaQL query!');
                return;
            }
            
            const loading = document.getElementById('loading');
            const output = document.getElementById('output');
            const sqlOutput = document.getElementById('sqlOutput');
            
            loading.style.display = 'block';
            output.textContent = '';
            sqlOutput.textContent = '';
            
            fetch('/api/compile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                displayResults(data);
                displaySQL(data);
                displayStats(data);
                queryCount++;
            })
            .catch(error => {
                loading.style.display = 'none';
                output.innerHTML = '<span class="error">Network Error: ' + error.message + '</span>';
            });
        }
        
        function displayResults(data) {
            const output = document.getElementById('output');
            let html = '';
            
            if (data.success) {
                html += '<span class="success">✅ ' + data.message + '</span>\\n\\n';
                
                if (data.results && data.results.length > 0) {
                    data.results.forEach((result, index) => {
                        html += '<strong>Query ' + (index + 1) + ':</strong> ' + result.message + '\\n';
                        
                        if (result.data && result.data.length > 0) {
                            html += '<table class="result-table">\\n';
                            html += '<tr>';
                            result.columns.forEach(col => {
                                html += '<th>' + col + '</th>';
                            });
                            html += '</tr>\\n';
                            
                            result.data.forEach(row => {
                                html += '<tr>';
                                result.columns.forEach(col => {
                                    html += '<td>' + (row[col] || '') + '</td>';
                                });
                                html += '</tr>\\n';
                            });
                            html += '</table>\\n';
                            html += '<small>Rows returned: ' + result.row_count + '</small>\\n\\n';
                        } else {
                            html += '<small>Affected rows: ' + result.affected_rows + '</small>\\n\\n';
                        }
                    });
                }
            } else {
                html += '<span class="error">❌ Query failed</span>\\n\\n';
            }
            
            if (data.errors && data.errors.length > 0) {
                html += '<strong>Errors:</strong>\\n';
                data.errors.forEach(error => {
                    html += '<span class="error">• ' + error + '</span>\\n';
                });
                html += '\\n';
            }
            
            if (data.warnings && data.warnings.length > 0) {
                html += '<strong>Warnings:</strong>\\n';
                data.warnings.forEach(warning => {
                    html += '<span class="warning">• ' + warning + '</span>\\n';
                });
            }
            
            output.textContent = html;
        }
        
        function displaySQL(data) {
            const sqlOutput = document.getElementById('sqlOutput');
            if (data.sql_statements && data.sql_statements.length > 0) {
                let sql = '<strong>Generated SQL:</strong>\\n\\n';
                data.sql_statements.forEach((statement, index) => {
                    sql += (index + 1) + '. ' + statement + ';\\n\\n';
                });
                sqlOutput.textContent = sql;
            } else {
                sqlOutput.textContent = 'No SQL generated';
            }
        }
        
        function displayStats(data) {
            document.getElementById('queryCount').textContent = queryCount;
            document.getElementById('executionTime').textContent = data.execution_time.toFixed(3) + 's';
            document.getElementById('affectedRows').textContent = data.affected_rows;
        }
        
        function clearInput() {
            document.getElementById('queryInput').value = '';
            document.getElementById('output').textContent = 'Results will appear here...';
            document.getElementById('sqlOutput').textContent = 'Generated SQL will appear here...';
        }
        
        function showExamples() {
            const examples = document.getElementById('examples');
            examples.style.display = examples.style.display === 'none' ? 'block' : 'none';
        }
        
        function setExample(query) {
            document.getElementById('queryInput').value = query;
        }
        
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.add('active');
            event.target.classList.add('active');
        }
        
        // Keyboard shortcuts
        document.getElementById('queryInput').addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                executeQuery();
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main web interface"""
    return send_from_directory('web', 'index.html')

@app.route('/api/compile', methods=['POST'])
def compile_query():
    """Compile and execute BhashaQL query"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "errors": ["No query provided"]
            }), 400
        
        query = data['query']
        if not query.strip():
            return jsonify({
                "success": False,
                "errors": ["Empty query"]
            }), 400
        
        # Set compiler options if provided
        if 'show_sql' in data:
            web_compiler.show_sql = data['show_sql']
        if 'show_ast' in data:
            web_compiler.show_ast = data['show_ast']
        if 'show_ir' in data:
            web_compiler.show_ir = data['show_ir']
        
        result = web_compiler.compile_and_execute_web(query)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "errors": [f"Server error: {str(e)}"]
        }), 500

@app.route('/api/examples')
def get_examples():
    """Get example BhashaQL queries"""
    examples = [
        {
            "category": "DDL",
            "description": "Create table",
            "query": "banaye table students (id number, name text, age number);"
        },
        {
            "category": "DML",
            "description": "Insert data",
            "query": "daalen mein students values (1, 'Aman', 20);"
        },
        {
            "category": "DQL",
            "description": "Select all",
            "query": "laye * se students;"
        },
        {
            "category": "DQL",
            "description": "Select with condition",
            "query": "laye * se students jahan age > 18;"
        },
        {
            "category": "DML",
            "description": "Update data",
            "query": "badlein students set karein age = 21 jahan id = 1;"
        },
        {
            "category": "DML",
            "description": "Delete data",
            "query": "mitayein se students jahan age < 18;"
        },
        {
            "category": "DQL",
            "description": "Count records",
            "query": "laye count(*) se students;"
        },
        {
            "category": "DQL",
            "description": "Order by",
            "query": "laye name, age se students order karein name;"
        }
    ]
    
    return jsonify({"examples": examples})

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "BhashaQL Web API",
        "version": "1.0.0"
    })

@app.route('/api/tables')
def get_tables():
    """Get list of all tables"""
    try:
        # Initialize connection if needed
        init_result = web_compiler.executor.initialize()
        if not init_result.success:
            return jsonify({
                "success": False,
                "error": init_result.message
            })
        
        tables = web_compiler.executor.db_manager.get_table_list()
        if tables.success:
            return jsonify({
                "success": True,
                "tables": [row['name'] for row in tables.data]
            })
        else:
            return jsonify({
                "success": False,
                "error": tables.message
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/stats')
def get_stats():
    """Get database and execution statistics"""
    try:
        compiler = get_compiler()
        stats = compiler.executor.get_execution_stats()
        db_info = compiler.executor.get_database_info()
        
        return jsonify({
            "execution_stats": stats,
            "database_info": db_info
        })
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == '__main__':
    os.makedirs('runtime', exist_ok=True)

    print("🚀 Starting BhashaQL Web Server...")
    print("📱 Open http://localhost:5000 in your browser")
    print("🔧 API available at http://localhost:5000/api")
    print("📚 Examples at http://localhost:5000/api/examples")
    print("❤️ Health check at http://localhost:5000/api/health")

    serve(app, host='0.0.0.0', port=5000)

    
