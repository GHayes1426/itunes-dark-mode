"""Visual assertions for the fixed Artists fixture; never decode library text."""
def check(payload, selected):
    visual=payload['visualChecks'];base=visual['before']
    assert len(payload['repaints'])==2
    if selected:assert base['rowColor']==[38,135,251], 'Expected active detail row'
    else:assert base['selection']==[38,135,251], 'Expected active Artists sidebar'
    for i,r in enumerate(payload['repaints'],1):
        f=visual[f'repaint-{i}']
        assert f['selection']==base['selection'] and f['tileHashes']==base['tileHashes'] and min(base['tileColors'])>1
        events=r.get('detail',r)['events']
        assert sum(bool(e.get('light')) for e in events)==(5 if selected else 6)
        for n,(a,b) in enumerate(zip(f['labels'],base['labels'])):
            if selected and n==1:
                assert f['rowColor']==base['rowColor'] and f['rowLabelHash']==base['rowLabelHash']
                assert any(e.get('d')==[745,333,870,355] and e.get('rgba')==[1,1,1,1] and not e.get('light') for e in events)
            else:assert a['darkBase']>a['lightInk']>100 and b['lightInk']>b['darkBase']
