
import sys, os
from flask import jsonify
from flask import Flask, render_template, redirect, url_for, request, flash
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.models import Request, CallHistory, KnowledgeBase

app = Flask(__name__)

# admin dashboard
@app.route('/')
def index():
    """Main dashboard view for supervisors"""
    # recent pending requests
    pending_requests = Request.get_pending_requests()[:20]
    print(f"Pending requests: {pending_requests}")
    learned_answers = KnowledgeBase.get_all()[:20]
    print(f"Learned answers: {learned_answers}")

    return render_template('dashboard.html', 
                          pending_requests=pending_requests,
                          learned_answers=learned_answers)

# route to get needed stats
@app.route('/stats', strict_slashes=False, methods=['GET'])
def stats():
    """Return needed stats for the dashboard."""
    pending_count = len(Request.get_pending_requests())
    all_requests = Request.get_request_history()
    resolved = [req for req in all_requests if req.status == 'resolved']
    resolved_count = len(resolved)
    unresolved = [req for req in all_requests if req.status == 'unresolved']
    unresolved_count = len(unresolved)
    call_history = CallHistory.get_all()
    total_calls = len(call_history)
    ai_handled_calls = len([call for call in call_history if call.ai_handled])

    ai_handled_ratio = (ai_handled_calls / total_calls * 100) if total_calls > 0 else 0

    return jsonify({
        "pending_count": pending_count,
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "ai_handled": round(ai_handled_ratio, 1),  # Rounded to 1 decimal place
        "total_calls": total_calls
    })

# route to get pending requests
@app.route('/requests/pending', strict_slashes=False)
def pending_requests():
    """View all pending requests"""
    requests = Request.get_pending_requests()
    return render_template('pending.html', pending_requests=requests)

# route to get resolved requests
@app.route('/requests/resolved', strict_slashes=False)
def resolved_requests():
    """View all resolved requests"""
    all_requests = Request.get_request_history()
    resolved = [req for req in all_requests if req.status == 'resolved']
    return render_template('resolved.html', resolved_requests=resolved)

# route to get unresolved requests
@app.route('/requests/unresolved', strict_slashes=False)
def unresolved_requests():
    """View all unresolved requests"""
    all_requests = Request.get_request_history()
    unresolved = [req for req in all_requests if req.status == 'unresolved']
    return render_template('unresolved.html', unresolved_requests=unresolved)

# route to get call history
@app.route('/calls/history', strict_slashes=False)
def call_history():
    """View call history"""
    calls = CallHistory.get_recent_calls(limit=100)
    return render_template('call_history.html', calls=calls)

# Route to handle resolving a request
@app.route('/requests/<call_id>/resolve', methods=['POST'], strict_slashes=False)
def resolve_request(call_id):
    """Resolve a request"""
    answer = request.form.get('answer', '')
    
    if not answer:
        flash('Please provide an answer', 'error')
        return redirect(url_for('pending_requests'))
    
    req = Request.get(call_id)
    if req:
        req.resolve(answer)
        flash('Request resolved successfully', 'success')
    else:
        flash('Request not found', 'error')
    
    return redirect(url_for('pending_requests'))

# Route to mark a request as unresolved
@app.route('/requests/<call_id>/unresolved', methods=['POST'], strict_slashes=False)
def mark_unresolved(call_id):
    """Mark a request as unresolved"""
    reason = request.form.get('reason', 'No reason provided')
    
    req = Request.get(call_id)
    if req:
        req.mark_unresolved(reason)
        flash('Request marked as unresolved', 'success')
    else:
        flash('Request not found', 'error')
    
    return redirect(url_for('pending_requests'))

# route to get knowledge base
@app.route('/knowledge', strict_slashes=False)
def knowledge_base():
    """View knowledge base entries"""
    entries = KnowledgeBase.get_all()
    return render_template('knowledge_base.html', entries=entries)

# route to add to knowledge base
@app.route('/knowledge/add', methods=['GET', 'POST'], strict_slashes=False)
def add_knowledge():
    """Add a new knowledge base entry"""
    if request.method == 'POST':
        key_phrase = request.form.get('key_phrase', '')
        question = request.form.get('question', '')
        answer = request.form.get('answer', '')
        
        if not all([key_phrase, question, answer]):
            flash('All fields are required', 'error')
            return render_template('add_knowledge.html')
        
        KnowledgeBase.create(key_phrase, question, answer, created_by='supervisor')
        flash('Knowledge base entry added', 'success')
        return redirect(url_for('knowledge_base'))
    
    return render_template('add_knowledge.html')

if __name__ == '__main__':
    app.run(debug=True)
 