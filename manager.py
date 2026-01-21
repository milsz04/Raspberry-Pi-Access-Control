import sys
import os
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from django.http import JsonResponse
#Add parent directory to path to import DatabaseManager"""
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from database_manager import DatabaseManager

db = DatabaseManager()

def check_update(request):
    logs = db.get_logs() # Pobieramy logi (są posortowane od najnowszego)
    
    if logs:
        # Zakładamy, że ID to pierwsza kolumna (indeks 0) pierwszego wiersza
        last_id = logs[0][0] 
        count = len(logs)
    else:
        last_id = 0
        count = 0
        
    return JsonResponse({'last_id': last_id, 'count': count})

def index(request):
    """Renders the main Dashboard with logs, stats, and auto-refresh"""
    raw_logs = db.get_logs()
    raw_users = db.get_all_users()

    logs = []
    if raw_logs:
        for item in raw_logs:
            # item = (id, timestamp, uid, granted, photo_path)
            
            # Formatting time string to remove milliseconds
            raw_time = item[1] if item[1] else "-"
            
           #SQLite says "2026-01-15 14:30:05.123

            formatted_time = str(raw_time)[:19] 

            # Checking if photo exists
            photo_path = item[4]
            if photo_path == "" or photo_path == "None":
                photo_path = None

            logs.append({
                'time': formatted_time,  
                'uid': item[2],
                'granted': item[3],
                'photo': photo_path
            })

    users = []
    if raw_users:
        for item in raw_users:
            users.append({'uid': item[0], 'name': item[1]})

    stats = {
        'total': len(logs),
        'granted': len([x for x in logs if x['granted']]),
        'denied': len([x for x in logs if not x['granted']])
    }
    latest_id = raw_logs[0][0] if raw_logs else 0
    

    return render(request, 'dashboard.html', {
        'logs': logs, 
        'users': users, 
        'stats': stats, 
        'latest_id': latest_id 
    })
    


def manage_view(request):
    """ Renders the Management page (Add/Remove users) without auto-refresh"""
    raw_users = db.get_all_users()
    users = []
    if raw_users:
        for item in raw_users:
            users.append({'uid': item[0], 'name': item[1]})
            
    return render(request, 'manage_users.html', {'users': users})


@csrf_exempt
def add_user(request):
    """Handles the POST request to add a new user to the database"""
    if request.method == 'POST':
        uid = request.POST.get('uid')
        name = request.POST.get('name')
        if uid and name:
            db.add_user(uid, name)
    return redirect('manage')  

@csrf_exempt
def remove_user(request):
    """Handles the POST request to remove a user from the database"""
    if request.method == 'POST':
        uid = request.POST.get('uid')
        if uid:
            db.remove_user(uid)
    return redirect('manage')  