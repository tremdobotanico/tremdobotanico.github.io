"""Lê os calendários (iCal) do Airbnb e do Booking e grava disponibilidade.json.

Os links ficam nos secrets do repositório (nunca neste arquivo):
ICAL_ESTUDIO_AIRBNB, ICAL_ESTUDIO_BOOKING, ICAL_KITNET_AIRBNB, ICAL_KITNET_BOOKING.
Grava só as noites ocupadas, sem nome de hóspede nem valores.
Se um calendário falhar, mantém os dados anteriores daquela unidade.
"""
import datetime as dt, json, os, re, sys, urllib.request

UNITS = {
    'estudio': ['ICAL_ESTUDIO_AIRBNB', 'ICAL_ESTUDIO_BOOKING'],
    'kitnet': ['ICAL_KITNET_AIRBNB', 'ICAL_KITNET_BOOKING'],
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'disponibilidade.json')
DAYS_AHEAD = 180


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'tremdobotanico-calendario/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def parse_date(v):
    m = re.search(r'(\d{8})', v)
    return dt.date(int(m[1][:4]), int(m[1][4:6]), int(m[1][6:8])) if m else None


def busy_nights(ics):
    if 'BEGIN:VCALENDAR' not in ics:
        raise ValueError('resposta não é um calendário')
    text = re.sub(r'\r?\n[ \t]', '', ics)  # junta linhas dobradas
    nights = set()
    for ev in text.split('BEGIN:VEVENT')[1:]:
        s = e = None
        for line in ev.splitlines():
            if line.startswith('DTSTART'):
                s = parse_date(line.split(':', 1)[1])
            elif line.startswith('DTEND'):
                e = parse_date(line.split(':', 1)[1])
        if not s:
            continue
        e = e or s + dt.timedelta(days=1)
        d = s
        while d < e:  # DTEND é o dia da saída: essa noite fica livre
            nights.add(d)
            d += dt.timedelta(days=1)
    return nights


def main():
    today = dt.date.today()
    limit = today + dt.timedelta(days=DAYS_AHEAD)
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT)).get('units', {})
        except Exception:
            old = {}
    units, problems = {}, []
    for unit, secrets in UNITS.items():
        urls = [os.environ.get(s, '').strip() for s in secrets]
        urls = [u for u in urls if u]
        if not urls:
            problems.append(f'{unit}: nenhum link configurado')
            if unit in old:
                units[unit] = old[unit]
            continue
        try:
            nights = set()
            for u in urls:
                nights |= busy_nights(fetch(u))
            busy = sorted(d.isoformat() for d in nights if today <= d <= limit)
            units[unit] = {'busy': busy, 'checked': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes')}
        except Exception as exc:
            problems.append(f'{unit}: {exc}')
            if unit in old:
                units[unit] = old[unit]
    data = {'from': today.isoformat(), 'until': limit.isoformat(), 'units': units}
    with open(OUT, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    for p in problems:
        print('AVISO', p, file=sys.stderr)


if __name__ == '__main__':
    main()
