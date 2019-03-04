from django.shortcuts import render
from django.http import HttpResponse


from controller.models import CatalogHistory

# Create your views here.
def front_main(request):
    message = 'Hello Django !!'
    return render(request, 'base.html', {
        'message': message,
    })


def history_menu(request):
    c_histories = CatalogHistory.objects.all()
    return render(request, 'histories.html', {
        'histories': c_histories,
    }) 


def catalog_details(request, pk):
    try:
        details = CatalogHistory.objects.get(pk=pk)
    except CatalogHistory.DoesNotExist:
        msg = []
        msg.append('Selected Item does not exist in Django DB.')
        msg.append('Check ID in your URL : \'/history/<ID>\'')
        return render(request, 'redirect.html', {
            'msg': msg
            })
    return render(request, 'details.html', {
        'details': details
        })


def upload_menu(request):
    return HttpResponse('Uploading menu here !!')


def page_not_found(request):
    return HttpResponse('Page Not Found ...')