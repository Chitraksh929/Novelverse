from datetime import datetime
import math

def time_ago(dt_str):
    if not dt_str: return ''
    try:
        dt = datetime.strptime(str(dt_str)[:19], '%Y-%m-%d %H:%M:%S')
    except:
        return str(dt_str)[:10]
    diff = (datetime.utcnow() - dt).total_seconds()
    if diff < 60:    return 'just now'
    if diff < 3600:  return f'{int(diff//60)}m ago'
    if diff < 86400: return f'{int(diff//3600)}h ago'
    if diff < 604800:return f'{int(diff//86400)}d ago'
    return dt.strftime('%b %d, %Y')

def word_count(text):
    if not text: return 0
    return len(text.split())

def paginate(total, page, per_page):
    pages = math.ceil(total / per_page)
    return {
        'page': page, 'pages': pages, 'total': total, 'per_page': per_page,
        'has_prev': page > 1, 'has_next': page < pages,
        'prev': page - 1, 'next': page + 1,
        'iter_pages': list(range(max(1, page-2), min(pages+1, page+3)))
    }
