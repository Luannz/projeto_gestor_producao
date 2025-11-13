# qualidade/views/auth.py
"""
Views de autenticação (login/logout)
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages


def login_view(request):
    """Página de login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha incorretos')
    
    return render(request, 'qualidade/login.html')


def logout_view(request):
    """Logout"""
    logout(request)
    return redirect('login')