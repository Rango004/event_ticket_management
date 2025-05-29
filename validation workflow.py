def validate_ticket_api(request):
    code = request.GET.get('code') or json.loads(request.body).get('code')
    ticket = Ticket.objects.get(unique_code=code)
    if ticket.status == 'PURCHASED':
        ticket.status = 'USED'
        ticket.save()
        return JsonResponse({'status': 'success', 'audio_feedback': 'success'})