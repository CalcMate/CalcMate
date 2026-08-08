import sys
sys.stdout.reconfigure(encoding='utf-8')

html = open('data/workspace/_site/weekly-holiday-allowance/index.html', encoding='utf-8').read()
if 'weekly holiday pay' in html:
    print('FAIL: "weekly holiday pay" (영문 변환) 발견됨')
elif '주휴수당' in html:
    idx = html.find('주휴수당')
    print('OK: "주휴수당" 정상 존재')
    print('  context:', repr(html[max(0, idx-60):idx+80]))
else:
    print('FAIL: 주휴수당 없음')
