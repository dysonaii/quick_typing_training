import json
import os
import random
import time
import PySimpleGUI as sg
from two_key_classification import two_key_classification, CATEGORIES
from shorthand_roots import SHORTHAND_ROOTS

SETTINGS_FILE = 'settings.json'

def parse_cin(path):
    result = {}
    in_chardef = False
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('%chardef'):
                in_chardef = True
                continue
            if not in_chardef or not line or line.startswith('#') or line.startswith('%'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                result.setdefault(parts[0], []).append(parts[1])
    return result

def build_one_key(cin, letter_start='A', letter_end='Z'):
    letters = [c for c in 'abcdefghijklmnopqrstuvwxyz']
    si = letters.index(letter_start.lower())
    ei = letters.index(letter_end.lower())
    target = set(letters[si:ei+1])
    return [(char, ks) for ks, chars in cin.items() if len(ks) == 1 and ks in target for char in chars]

def build_two_key(cin, category, letter_start=None, letter_end=None):
    result = []
    letters = sorted(two_key_classification.keys())
    if letter_start and letter_end:
        si = letters.index(letter_start)
        ei = letters.index(letter_end)
        target = letters[si:ei+1]
    else:
        target = letters
    for ltr in target:
        cats = two_key_classification[ltr]
        for char in cats.get(category, ''):
            for ks, chars in cin.items():
                if len(ks) == 2 and ks[0].upper() == ltr and char in chars:
                    result.append((char, ks))
                    break
    return result

def compute_shortest(cin):
    shortest = {}
    for ks, chars in cin.items():
        for ch in chars:
            if ch not in shortest or len(ks) < len(shortest[ch]):
                shortest[ch] = ks
    return shortest

def build_speed_gen(shortest, letter_start, letter_end, min_len, max_len):
    letters = sorted(SHORTHAND_ROOTS.keys())
    si = letters.index(letter_start)
    ei = letters.index(letter_end)
    codes = []
    for ltr in letters[si:ei+1]:
        for root in SHORTHAND_ROOTS[ltr]:
            code = shortest.get(root, '')
            if len(code) == 2:
                codes.append(code)
    suffixes = set(codes)
    result = []
    for ch, k in shortest.items():
        o = ord(ch)
        if 0x3105 <= o <= 0x3129:
            continue
        ln = len(k)
        if ln < 2:
            continue
        if min_len and ln < min_len:
            continue
        if max_len and ln > max_len:
            continue
        if k[-2:] in suffixes:
            result.append((ch, k))
    return result

MODES = [
    ('一碼', 'one_key', None),
    ('二碼(標準)', 'two_key', 'standard'),
    ('二碼(頭尾)', 'two_key', 'headtail'),
    ('二碼(簡速)', 'two_key', 'shorthand'),
    ('二碼(簡字)', 'two_key', 'simplified'),
    ('二碼(其它)', 'two_key', 'other'),
    ('二碼(未分類)', 'two_key', 'other2'),
    ('速根', 'speed_gen', 'speed_gen'),
]

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_settings(mode_idx, random_mode, letter_start, letter_end, code_start='2', code_end='3', cin_path='', answer_delay=2):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'mode': mode_idx, 'random': random_mode,
                       'letter_start': letter_start, 'letter_end': letter_end,
                       'code_start': code_start, 'code_end': code_end,
                       'cin_path': cin_path, 'answer_delay': answer_delay}, f)
    except Exception:
        pass

def main():
    sg.theme('LightBlue2')

    settings = load_settings()
    init_mode = settings.get('mode', 0)
    init_random = settings.get('random', True)
    init_ls = settings.get('letter_start', 'A')
    init_le = settings.get('letter_end', 'Z')
    init_cs = settings.get('code_start', '2')
    init_ce = settings.get('code_end', '3')
    init_cin = settings.get('cin_path', '')
    init_ad = settings.get('answer_delay', 2)

    cin = None
    shortest = None

    def parse_and_set(path):
        nonlocal cin, shortest
        cin = parse_cin(path)
        if not cin:
            raise ValueError('檔案不含字根資料')
        shortest = compute_shortest(cin)

    cin_path = init_cin
    if not cin_path or not os.path.exists(cin_path):
        cin_path = sg.popup_get_file('請選擇字根檔 (.cin)', file_types=(('CIN', '*.cin'),),
                                     title='載入字根檔')
    if not cin_path:
        sg.popup_error('未選擇字根檔，程式結束')
        return
    try:
        parse_and_set(cin_path)
    except Exception as e:
        sg.popup_error(f'載入失敗: {e}\n程式結束')
        return

    radio_row = [sg.Radio('隨機', 'MODE', key='-RANDOM-', default=init_random, enable_events=True),
                 sg.Radio('依序', 'MODE', key='-SEQ-', default=not init_random, enable_events=True),
                 sg.Text('答案停留(秒):', font=('Helvetica', 10)),
                 sg.Combo(list(range(1, 11)), default_value=init_ad, key='-ANSWER_DELAY-', size=(4, 1),
                          enable_events=True, readonly=True, font=('Helvetica', 10))]

    mode_buttons = []
    for i, (label, _, _) in enumerate(MODES):
        mode_buttons.append(sg.Button(f'{i+1}-{label}', key=f'-MODE{i}-', size=(14, 1),
                                       button_color=('white', 'darkblue') if i == init_mode else sg.theme_button_color()))

    letter_filter = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    layout = [
        [sg.Text('無蝦米快打練習', font=('Helvetica', 16)),
         sg.Push(),
         sg.Text(os.path.basename(cin_path), key='-CIN_NAME-', font=('Helvetica', 10),
                 text_color='#336699'),
         sg.Button('載入字根檔', key='-LOAD_CIN-', font=('Helvetica', 10)),
         sg.Button('離開', key='-EXIT-', font=('Helvetica', 10))],
        [sg.Column([mode_buttons[i:i+4] for i in range(0, len(mode_buttons), 4)])],
        [sg.Text('字群:', font=('Helvetica', 10)),
         sg.Combo(letter_filter, default_value=init_ls, key='-LETTER_START-', size=(3, 1),
                  enable_events=True, readonly=True, font=('Helvetica', 10)),
         sg.Text('~', font=('Helvetica', 10)),
         sg.Combo(letter_filter, default_value=init_le, key='-LETTER_END-', size=(3, 1),
                  enable_events=True, readonly=True, font=('Helvetica', 10)),
         sg.Push(),
         sg.Text('速根碼數:', font=('Helvetica', 10)),
         sg.Combo(['2', '3', '多'], default_value=init_cs, key='-CODE_START-', size=(3, 1),
                  enable_events=True, readonly=True, font=('Helvetica', 10)),
         sg.Text('~', font=('Helvetica', 10)),
         sg.Combo(['2', '3', '多'], default_value=init_ce, key='-CODE_END-', size=(3, 1),
                  enable_events=True, readonly=True, font=('Helvetica', 10))],
        radio_row,
        [sg.Text('題目', font=('Helvetica', 12)),
         sg.Text('', key='-QUESTION-', size=(8, 1), font=('Helvetica', 24), relief='sunken', justification='center')],
        [sg.Text('輸入', font=('Helvetica', 12)),
         sg.Text('', key='-INPUT-', size=(8, 1), font=('Helvetica', 24), relief='sunken', justification='center',
                 background_color='white')],
        [sg.Text('答案', font=('Helvetica', 12)),
         sg.Text('', key='-ANSWER-', size=(8, 1), font=('Helvetica', 24), relief='sunken', justification='center',
                 text_color='red'),
         sg.Button('查看', key='-REVEAL-', font=('Helvetica', 12))],
        [sg.Text('進度: 0/0', key='-PROGRESS-', font=('Helvetica', 10))],
        [sg.Text('', key='-MSG-', font=('Helvetica', 12), text_color='green')],
    ]

    window = sg.Window('無蝦米快打', layout, finalize=True, return_keyboard_events=True)

    bank = []
    original_bank = []
    current = None
    mistakes = 0
    seq_idx = 0
    typing = ''
    show_answer_until = 0
    start_time = 0
    current_mode = None  # (build_type, category)

    def get_code_range():
        ls_map = {'2': 2, '3': 3, '多': 4}
        le_map = {'2': 2, '3': 3, '多': None}
        s = ls_map[window['-CODE_START-'].get()]
        e = le_map[window['-CODE_END-'].get()]
        if e is not None and e < s:
            e = s
        return s, e

    def reload_bank():
        nonlocal bank, original_bank, current, mistakes, seq_idx, typing, show_answer_until, start_time
        if current_mode is None:
            return
        build_type, category = current_mode
        ls = window['-LETTER_START-'].get()
        le = window['-LETTER_END-'].get()
        if build_type == 'one_key':
            bank = build_one_key(cin, ls, le)
        elif build_type == 'speed_gen':
            s, e = get_code_range()
            bank = build_speed_gen(shortest, ls, le, s, e)
        else:
            bank = build_two_key(cin, category, ls, le)
        original_bank = list(bank)
        if not window['-SEQ-'].get():
            random.shuffle(bank)
        else:
            bank.sort(key=lambda x: x[1])
        current = None
        mistakes = 0
        seq_idx = 0
        typing = ''
        show_answer_until = 0
        start_time = time.time()
        next_question()

    def load_mode(mode_idx):
        nonlocal current_mode
        _, build_type, category = MODES[mode_idx]
        current_mode = (build_type, category)
        reload_bank()

    def next_question():
        nonlocal current, mistakes, seq_idx, typing, show_answer_until
        if not bank:
            elapsed = time.time() - start_time
            m, s = divmod(int(elapsed), 60)
            window['-QUESTION-'].update('完成!')
            window['-ANSWER-'].update('')
            window['-MSG-'].update(f'這一組練完了! 花費 {m}分{s}秒')
            window['-PROGRESS-'].update(f'進度: 0/{len(original_bank)}')
            return
        if window['-SEQ-'].get():
            current = bank[seq_idx % len(bank)]
        else:
            current = random.choice(bank)
        mistakes = 0
        typing = ''
        show_answer_until = 0
        window['-QUESTION-'].update(current[0])
        window['-ANSWER-'].update('')
        window['-INPUT-'].update('')
        window['-MSG-'].update('')
        window['-PROGRESS-'].update(f'進度: {len(bank)}/{len(original_bank)}')

    def reveal_answer():
        if current is None:
            return
        window['-ANSWER-'].update(current[1].upper())

    def check_answer():
        nonlocal mistakes, seq_idx, typing, show_answer_until
        if current is None or not typing:
            return
        keystroke = current[1]
        if typing == keystroke:
            bank.remove(current)
            if not window['-SEQ-'].get():
                seq_idx += 1
            window['-MSG-'].update('答對了!', text_color='green')
            typing = ''
            next_question()
        else:
            mistakes += 1
            if mistakes >= 3:
                window['-ANSWER-'].update(keystroke.upper())
                window['-MSG-'].update(f'答案: {keystroke.upper()}', text_color='red')
                typing = ''
                show_answer_until = time.time() + last_ad
            else:
                window['-MSG-'].update(f'錯了 ({mistakes}/3)', text_color='orange')
                typing = ''
                window['-INPUT-'].update('')

    def valid_key(event):
        return len(event) == 1 and event.lower() in 'abcdefghijklmnopqrstuvwxyz,.\'[]'

    def highlight_mode(idx):
        for i in range(len(MODES)):
            color = ('white', 'darkblue') if i == idx else sg.theme_button_color()
            window[f'-MODE{i}-'].update(button_color=color)

    last_mode_idx = init_mode
    last_random = init_random
    last_ls = init_ls
    last_le = init_le
    last_cs = init_cs
    last_ce = init_ce
    last_cin_path = cin_path
    last_ad = init_ad
    load_mode(init_mode)
    highlight_mode(init_mode)

    def do_save():
        save_settings(last_mode_idx, last_random, last_ls, last_le, last_cs, last_ce, last_cin_path, last_ad)

    while True:
        event, values = window.read(timeout=100)
        if event == sg.WIN_CLOSED or event == '-EXIT-':
            do_save()
            break

        if show_answer_until > 0:
            if time.time() >= show_answer_until:
                show_answer_until = 0
                if not window['-SEQ-'].get():
                    seq_idx += 1
                next_question()
                continue

        for i in range(len(MODES)):
            if event == f'-MODE{i}-':
                last_mode_idx = i
                load_mode(i)
                highlight_mode(i)
                break

        if event in ('-LETTER_START-', '-LETTER_END-'):
            last_ls = window['-LETTER_START-'].get()
            last_le = window['-LETTER_END-'].get()
            reload_bank()
        elif event in ('-CODE_START-', '-CODE_END-'):
            last_cs = window['-CODE_START-'].get()
            last_ce = window['-CODE_END-'].get()
            if current_mode:
                reload_bank()
        elif event in ('-RANDOM-', '-SEQ-'):
            last_random = window['-RANDOM-'].get()
            if current_mode:
                reload_bank()
        elif event == '-ANSWER_DELAY-':
            last_ad = int(window['-ANSWER_DELAY-'].get())
        elif event == '-REVEAL-':
            reveal_answer()
        elif event == '-LOAD_CIN-':
            new_path = sg.popup_get_file('選擇字根檔 (.cin)', file_types=(('CIN', '*.cin'),))
            if new_path:
                try:
                    parse_and_set(new_path)
                    last_cin_path = new_path
                    window['-CIN_NAME-'].update(os.path.basename(new_path))
                    if current_mode:
                        reload_bank()
                except Exception as e:
                    sg.popup_error(f'載入失敗: {e}')
        elif event.startswith('space') or event == ' ':
            if not bank and current_mode:
                reload_bank()
            else:
                check_answer()
        elif event.startswith('BackSpace'):
            typing = typing[:-1]
            window['-INPUT-'].update(typing)
        elif valid_key(event):
            typing += event.lower()
            window['-INPUT-'].update(typing)

    window.close()

if __name__ == '__main__':
    main()
