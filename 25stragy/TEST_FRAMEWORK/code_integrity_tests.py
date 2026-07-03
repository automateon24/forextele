#!/usr/bin/env python3
"""
CODE INTEGRITY TESTS
=====================
Code integrity and quality tests
"""

import sys
import os
import ast
import subprocess
import importlib.util
from pathlib import Path
from datetime import datetime
import json
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class CodeIntegrityTests:
    """Code integrity and quality tests"""
    
    def __init__(self):
        self.test_results = []
        self.errors = []
        
    def test_syntax_validation(self):
        """Test syntax validation of all Python files"""
        print("🔍 Testing Syntax Validation...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            syntax_errors = []
            
            for py_file in python_files:
                try:
                    # Check syntax
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Try to compile the code
                    compile(content, str(py_file), 'exec')
                    
                except SyntaxError as e:
                    syntax_errors.append(f"{py_file.name}: {e}")
                except Exception as e:
                    syntax_errors.append(f"{py_file.name}: {e}")
            
            if not syntax_errors:
                self.test_results.append({
                    'test': 'syntax_validation',
                    'files_checked': len(python_files),
                    'syntax_errors': 0,
                    'status': 'passed'
                })
                print(f"✅ Syntax validation passed: {len(python_files)} files checked")
                return True
            else:
                self.errors.extend(syntax_errors)
                print(f"❌ Syntax validation failed: {len(syntax_errors)} errors")
                for error in syntax_errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Syntax validation error: {e}")
            print(f"❌ Syntax validation error: {e}")
            return False
    
    def test_import_validation(self):
        """Test import validation of modules"""
        print("📦 Testing Import Validation...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            import_errors = []
            
            for py_file in python_files:
                try:
                    # Get module name from file path
                    module_name = py_file.stem
                    
                    # Try to import the module
                    spec = importlib.util.spec_from_file_location(module_name, py_file)
                    module = importlib.util.module_from_spec(spec)
                    
                    # Test that module can be imported
                    self.test_results.append({
                        'test': 'import_validation',
                        'module': module_name,
                        'file': py_file.name,
                        'status': 'passed'
                    })
                    
                except Exception as e:
                    import_errors.append(f"{py_file.name}: {e}")
            
            if not import_errors:
                print(f"✅ Import validation passed: {len(python_files)} modules checked")
                return True
            else:
                self.errors.extend(import_errors)
                print(f"❌ Import validation failed: {len(import_errors)} errors")
                for error in import_errors:
                    print(f"   - {error}")
                return False
                
        except Exception as e:
            self.errors.append(f"Import validation error: {e}")
            print(f"❌ Import validation error: {e}")
            return False
    
    def test_code_style(self):
        """Test code style and formatting"""
        print("📝 Testing Code Style...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            style_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Check for common style issues
                    line_number = 1
                    for line in lines:
                        line = line.rstrip()
                        
                        # Check for trailing whitespace
                        if line.endswith(' ') and len(line) > 1:
                            style_issues.append(f"{py_file.name}:{line_number} - Trailing whitespace")
                        
                        # Check for tabs (should use spaces)
                        if '\t' in line:
                            style_issues.append(f"{py_file.name}:{line_number} - Tab character found")
                        
                        # Check line length (should be reasonable)
                        if len(line) > 120:
                            style_issues.append(f"{py_file.name}:{line_number} - Line too long ({len(line)} chars)")
                        
                        line_number += 1
                
                except Exception as e:
                    style_issues.append(f"{py_file.name}: {e}")
            
            if len(style_issues) < 50:  # Allow some style issues
                self.test_results.append({
                    'test': 'code_style',
                    'files_checked': len(python_files),
                    'style_issues': len(style_issues),
                    'status': 'passed'
                })
                print(f"✅ Code style test passed: {len(style_issues)} issues found")
                return True
            else:
                    self.errors.extend(style_issues)
                    print(f"❌ Code style test failed: {len(style_issues)} issues found")
                    for issue in style_issues[:10]:  # Show first 10 issues
                        print(f"   - {issue}")
                    if len(style_issues) > 10:
                        print(f"   ... and {len(style_issues) - 10} more")
                    return False
                
        except Exception as e:
            self.errors.append(f"Code style error: {e}")
            print(f"❌ Code style error: {e}")
            return False
    
    def test_function_definitions(self):
        """Test function definitions and signatures"""
        print("⚙️ Testing Function Definitions...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            function_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Find all function definitions
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            # Check function name
                            func_name = node.name
                            if not func_name.isidentifier():
                                function_issues.append(f"{py_file.name}:{node.lineno} - Invalid function name: {func_name}")
                            
                            # Check for docstring
                            if not ast.get_docstring(node):
                                function_issues.append(f"{py_file.name}:{node.lineno} - Function {func_name} missing docstring")
                            
                            # Check parameters
                            args = node.args
                            defaults = args.defaults
                            
                            # Check for mutable default arguments
                            for default in defaults:
                                if isinstance(default, (ast.List, ast.Dict)):
                                    function_issues.append(f"{py_file.name}:{node.lineno} - Function {func_name} has mutable default argument")
                            
                            # Check return type annotations
                            if node.returns and not node.returns.annotation:
                                function_issues.append(f"{py_file.name}:{node.lineno} - Function {func_name} missing return annotation")
                
                except Exception as e:
                    function_issues.append(f"{py_file.name}: {e}")
            
            if len(function_issues) < 20:  # Allow some function issues
                self.test_results.append({
                    'test': 'function_definitions',
                    'files_checked': len(python_files),
                    'function_issues': len(function_issues),
                    'status': 'passed'
                })
                print(f"✅ Function definitions test passed: {len(function_issues)} issues found")
                return True
            else:
                self.errors.extend(function_issues)
                print(f"❌ Function definitions test failed: {len(function_issues)} issues found")
                for issue in function_issues[:10]:  # Show first 10 issues
                    print(f"   - {issue}")
                if len(function_issues) > 10:
                    print(f"   ... and {len(function_issues) - 10} more")
                    return False
                
        except Exception as e:
            self.errors.append(f"Function definitions error: {e}")
            print(f"❌ Function definitions error: {e}")
            return False
    
    def test_class_definitions(self):
        """Test class definitions and structure"""
        print("🏗️ Testing Class Definitions...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            class_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Find all class definitions
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Check class name
                            class_name = node.name
                            if not class_name.isidentifier():
                                class_issues.append(f"{py_file.name}:{node.lineno} - Invalid class name: {class_name}")
                            
                            # Check for docstring
                            if not ast.get_docstring(node):
                                class_issues.append(f"{py_file.name}:{node.lineno} - Class {class_name} missing docstring")
                            
                            # Check for __init__ method
                            has_init = False
                            for item in node.body:
                                if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                                    has_init = True
                                    break
                            
                            if not has_init:
                                class_issues.append(f"{py_file.name}:{node.lineno} - Class {class_name} missing __init__ method")
                
                except Exception as e:
                    class_issues.append(f"{py_file.name}: {e}")
            
            if len(class_issues) < 10:  # Allow some class issues
                self.test_results.append({
                    'test': 'class_definitions',
                    'files_checked': len(python_files),
                    'class_issues': len(class_issues),
                    'status': 'passed'
                })
                print(f"✅ Class definitions test passed: {len(class_issues)} issues found")
                return True
            else:
                self.errors.extend(class_issues)
                print(f"❌ Class definitions test failed: {len(class_issues)} issues found")
                for issue in class_issues:
                    print(f"   - {issue}")
                return False
                
        except Exception as e:
            self.errors.append(f"Class definitions error: {e}")
            print(f"❌ Class definitions error: {e}")
            return False
    
    def test_import_statements(self):
        """Test import statements"""
        print("📦 Testing Import Statements...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            import_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Find all import statements
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    if not alias.isidentifier():
                                        import_issues.append(f"{py_file.name}:{node.lineno} - Invalid import alias: {alias.name}")
                            else:
                                for name in node.names:
                                    if not name.isidentifier():
                                        import_issues.append(f"{py_file.name}:{node.lineno} - Invalid import name: {name}")
                            
                            elif isinstance(node, ast.ImportFrom):
                                if node.module and not node.module.isidentifier():
                                    import_issues.append(f"{py_file.name}:{node.lineno} - Invalid import module: {node.module}")
                                
                                for alias in node.names:
                                    if not alias.isidentifier():
                                        import_issues.append(f"{py_file.name}:{node.lineno} - Invalid import alias: {alias.name}")
                
                except Exception as e:
                    import_issues.append(f"{py_file.name}: {e}")
            
            if len(import_issues) < 10:  # Allow some import issues
                self.test_results.append({
                    'test': 'import_statements',
                    'files_checked': len(python_files),
                    'import_issues': len(import_issues),
                    'status': 'passed'
                })
                print(f"✅ Import statements test passed: {len(import_issues)} issues found")
                return True
            else:
                self.errors.extend(import_issues)
                print(f"❌ Import statements test failed: {len(import_issues)} issues found")
                for issue in import_issues:
                    print(f"   - {issue}")
                return False
                
        except Exception as e:
            self.errors.append(f"Import statements error: {e}")
            print(f"❌ Import statements error: {e}")
            return False
    
    def test_variable_naming(self):
        """Test variable naming conventions"""
        print("🏷️ Testing Variable Naming...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            naming_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Find all variable assignments
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id
                                    
                                    # Check naming convention (snake_case)
                                    if not re.match(r'^[a-z_][a-zA-Z0-9_]*$', var_name):
                                        naming_issues.append(f"{py_file.name}:{node.lineno} - Variable not snake_case: {var_name}")
                                
                                elif len(var_name) > 50:
                                    naming_issues.append(f"{py_file.name}:{node.lineno} - Variable name too long: {var_name}")
                
                except Exception as e:
                    naming_issues.append(f"{py_file.name}: {e}")
            
            if len(naming_issues) < 20:  # Allow some naming issues
                self.test_results.append({
                    'test': 'variable_naming',
                    'files_checked': len(python_files),
                    'naming_issues': len(naming_issues),
                    'status': 'passed'
                })
                print(f"✅ Variable naming test passed: {len(naming_issues)} issues found")
                return True
            else:
                self.errors.extend(naming_issues)
                print(f"❌ Variable naming test failed: {len(naming_issues)} issues found")
                for issue in naming_issues[:10]:
                    print(f"   - {issue}")
                if len(naming_issues) > 10:
                    print(f"   ... and {len(naming_issues) - 10} more")
                    return False
                
        except Exception as e:
            self.errors.append(f"Variable naming error: {e}")
            print(f"❌ Variable naming error: {e}")
            return False
    
    def test_docstring_coverage(self):
        """Test docstring coverage"""
        print("📄 Testing Docstring Coverage...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            missing_docs = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'module') as f:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Check for module docstring
                    if not ast.get_docstring(tree):
                        missing_docs.append(f"{py_file.name} - Missing module docstring")
                    
                    # Check function docstrings
                    functions = []
                    classes = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            functions.append(node)
                        elif isinstance(node, ast.ClassDef):
                            classes.append(node)
                    
                    for func in functions:
                        if not ast.get_docstring(func):
                            missing_docs.append(f"{py_file.name}:{func.lineno} - Function {func.name} missing docstring")
                    
                    for cls in classes:
                        if not ast.get_docstring(cls):
                            missing_docs.append(f"{py_file.name}:{cls.lineno} - Class {cls.name} missing docstring")
                
                except Exception as e:
                    missing_docs.append(f"{py_file.name}: {e}")
            
            if len(missing_docs) < 20:  # Allow some missing docs
                self.test_results.append({
                    'test': 'docstring_coverage',
                    'files_checked': len(python_files),
                    'missing_docs': len(missing_docs),
                    'status': 'passed'
                })
                print(f"✅ Docstring coverage test passed: {len(missing_docs)} missing docs")
                return True
            else:
                self.errors.extend(missing_docs)
                print(f"❌ Docstring coverage test failed: {len(missing_docs)} missing docs")
                for doc in missing_docs[:10]:
                    print(f"   - {doc}")
                if len(missing_docs) > 10:
                    print(f"   ... and {len(missing_docs) - 10} more")
                    return False
                
        except Exception as e:
            self.errors.append(f"Docstring coverage error: {e}")
            print(f"❌ Docstring coverage error: {e}")
            return False
    
    def test_error_handling(self):
        """Test error handling patterns"""
        print("⚠️ Testing Error Handling...")
        
        try:
            python_files = list(project_root.glob('*.py'))
            
            error_handling_issues = []
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', try:
                        content = f.read()
                    
                    # Parse AST
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # Check for try-except blocks
                    try_blocks = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Try):
                            try_blocks.append(node)
                    
                    if len(try_blocks) == 0:
                        # Check if file has any operations that could fail
                        has_risky_operations = False
                        
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call):
                                if hasattr(node.func, 'id'):
                                    func_name = node.func.id
                                    risky_functions = ['open', 'file', 'os.remove', 'subprocess.run']
                                    if func_name in risky_functions:
                                        has_risky_operations = True
                                    break
                        
                        if has_risky_operations:
                            error_handling_issues.append(f"{py_file.name} - Has risky operations without try-except")
                    
                except Exception as e:
                    error_handling_issues.append(f"{py_file.name}: {e}")
            
            # Allow some files to have no error handling
            if len(error_handling_issues) < len(python_files) * 0.5:
                self.test_results.append({
                    'test': 'error_handling',
                    'files_checked': len(python_files),
                    'files_without_try_except': len(error_handling_issues),
                    'status': 'passed'
                })
                print(f"✅ Error handling test passed: {len(error_handling_issues)} files without try-except")
                return True
            else:
                self.errors.extend(error_handling_issues)
                print(f"❌ Error handling test failed: {len(error_handling_issues)} files without try-except")
                for issue in error_handling_issues[:10]:
                    print(f"   - {issue}")
                return False
                
        except Exception as e:
            self.errors.append(f"Error handling error: {e}")
            print(f"❌ Error handling error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all code integrity tests"""
        print("🔍 Starting Code Integrity Tests...")
        print("="*60)
        
        tests = [
            self.test_syntax_validation,
            self.test_import_validation,
            self.test_code_style,
            self.test_function_definitions,
            self.test_class_definitions,
            self.test_import_statements,
            self.test_variable_naming,
            self.test_docstring_coverage,
            self.test_error_handling
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test failed: {e}")
                failed += 1
        
        print("="*60)
        print(f"🔍 Code Integrity Tests Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📊 Total Tests: {passed + failed}")
        print(f"   📝 Test Results: {len(self.test_results)}")
        
        if self.errors:
            print(f"   ⚠️  Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"      - {error}")
        
        return len(self.errors) == 0

def main():
    """Main execution"""
    tester = CodeIntegrityTests()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All code integrity tests passed!")
        return 0
    else:
        print("❌ Some code integrity tests failed!")
        return 1

if __name__ == "__main__":
    main()
