from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def front_main(request):
    message = 'Hello Django !!'
    return render(request, 'base.html', {
        'message': message,
    })



def history_menu(request):
    return HttpResponse('History menu here !!')

def upload_menu(request):
    return HttpResponse('Uploading menu here !!')

def page_not_found(request):
    return HttpResponse('Page Not Found ...')