import urwid, urwid.raw_display
import pexpect, pxssh
from xml.dom import minidom
import os, os.path, re, sys, time

################
__version__ = '0.4.0'
################

class NestedListWidget(urwid.WidgetWrap):
    def __init__(self, w_index, node, depth):
        self.node = node
        self.w_index = w_index
        self.depth = depth
        self.srch_text = ''
        self.widget = urwid.Text('')
        self.wrap = urwid.AttrWrap(self.widget, None) #!!
        self.wrap.attr = 'body'
        self.wrap.focus_attr = 'focus'
        self.update()
        super(NestedListWidget, self).__init__(self.wrap)

    def selectable(self):
        return True

    def keypress(self, (maxcol,), key):
        return key

class GroupWidget(NestedListWidget):
    def __init__(self, w_index, node, depth):
        super(GroupWidget, self).__init__(w_index, node, depth)

    def update(self):
        caption = self.node.getAttribute("name")
        self.widget.set_text( ["  "*(self.depth), ('mark', "+"), " ", caption] )
    
    def selectable(self):
        return False

class HostWidget(NestedListWidget):
    def __init__(self, w_index, node, depth):
        super(HostWidget, self).__init__(w_index, node, depth)

    def update(self):
        hostname = self.node.getAttribute("name")
        descr_tag = self.node.getElementsByTagName("description")[0]
        descr = descr_tag.getAttribute("line")
        self.srch_text = hostname
        caption = "  %s ( %s )" % (hostname, descr)
        self.widget.set_text(["  "*self.depth, caption])

class TreeWalker(urwid.ListWalker):
    def __init__(self, tree):
        self.widgets = []
        self.create_hosts_list(tree)
        self.focus = 0 # In fact, this is index in 'widgets' list
        self.filt = ''

    def create_hosts_list(self, node, depth = 0):
        """
            input - xml.dom Element object references to <hosts> config tag
            output - list of (node, depth) tulpes
            node - xml.dom Element object for <host> or <group> tag
            depth - tree-like depth of node
        """
        if node.nodeName == "host":
            idx = len(self.widgets)
            w = HostWidget(idx, node, depth)
            self.widgets.append(w)
            next_sibling = node.nextSibling
            if next_sibling:
                self.create_hosts_list(next_sibling, depth)
        elif node.nodeName == "group":
            idx = len(self.widgets)
            w = GroupWidget(idx, node, depth)
            self.widgets.append(w)
            if node.hasChildNodes:
                for child in node.childNodes:
                    self.create_hosts_list(child, depth + 1)
        elif node.nodeName == "hosts":
            for child in node.childNodes:
                self.create_hosts_list(child, depth)

    def set_filter(self, filter_str):
        self.filt = filter_str
        self._modified()

    def get_focus(self):
        widget = self.widgets[self.focus]
        if re.search(self.filt, widget.srch_text, re.I):
            return widget, self.focus
        else:
            return self.get_next(0)

    def get_widget_if_single(self):
        """
            Returns widget if it a single widget 
            in list (after filter is being applied)
        """
        cnt = 0
        w = None
        for widget in self.widgets:
            if re.search(self.filt, widget.srch_text, re.I):
                cnt += 1
                w = widget
        if cnt == 1:
            return w
        else:
            return None

    def set_focus(self, focus):
        self.focus = focus
        self._modified()

    def get_next(self, pos):
        while True:
            if pos < len(self.widgets) - 1:
                pos += 1
                widget = self.widgets[pos]
                if re.search(self.filt, widget.srch_text, re.I):
                    return widget, pos
            else: return None, None

    def get_prev(self, pos):
        while True:
            if pos > 0:
                pos -= 1
                widget = self.widgets[pos]
                if re.search(self.filt, widget.srch_text, re.I):
                    return widget, pos
            else: return None, None

class consoleui:
    palette = [
        ('body', 'white', 'black'),
        ('focus', 'black', 'dark cyan', 'standout'),
        ('foot', 'white', 'dark blue', 'standout'),
        ('head', 'black', 'dark blue'),
        ('key', 'light cyan', 'dark blue','underline'),
        ('title', 'white', 'dark blue', 'bold'),
        ('mark', 'light blue', 'black', 'bold'),
    ]

    title_text = [('title', "Screenex %s" % __version__)]
    list_legend_text = [
        ('key', "UP"), ",", ('key', "DOWN"), ",",
        ('key', "PGUP"), ",", ('key', "PGDN"),
        "  ",
        ('key', "Enter" ), "  ",
        ('key', "TAB"), "  ",
        ('key', "Q")
    ]
    search_legend_text = [
        ('key', "Enter" ), "  ",
        ('key', "TAB")
    ]

    def __init__(self, xmlroot):
        self.l_walker = TreeWalker(xmlroot)
        self.listbox = urwid.ListBox(self.l_walker)
        self.listbox.offset_rows = 1
        self.footer =urwid.AttrWrap(urwid.Edit("Search:"), 'foot')
        title = urwid.AttrWrap(urwid.Text(self.title_text), 'head')
        self.help = urwid.AttrWrap(urwid.Text(self.list_legend_text), 'head')
        self.header = urwid.Pile([title, self.help])
        self.focus_part = 'body'
        self.view = urwid.Frame( 
            urwid.AttrWrap(self.listbox, 'body'), 
            header = urwid.AttrWrap(self.header, 'head'), 
            footer = self.footer,
            focus_part = self.focus_part
        )

    def main(self):
        self.ui = urwid.raw_display.Screen()
        self.ui.register_palette(self.palette)
        self.ui.run_wrapper(self.run)
        self.ui.stop()
        return self.focus_node

    def run(self):
        """
            Handle user input and display updating.
        """
        self.ui.set_mouse_tracking()

        size = self.ui.get_cols_rows()
        while True:
            canvas = self.view.render(size, focus=1)
            self.ui.draw_screen(size, canvas)
            focus, _ign = self.listbox.body.get_focus()
            keys = None
            while not keys: 
                keys = self.ui.get_input()
            for k in keys:
                if urwid.is_mouse_event(k):
                    event, button, col, row = k
                    self.view.mouse_event(size,event, button, col, row, focus=True)
                    continue

                if k == 'window resize':
                    size = self.ui.get_cols_rows()
                    k = self.view.keypress(size, k)
                    continue                
                elif k == 'tab':
                    if self.focus_part == 'body':
                        self.focus_part = 'footer'
                        self.help.set_text(self.search_legend_text)
                    else:
                        self.focus_part = 'body'
                        self.help.set_text(self.list_legend_text)
                    self.view.set_focus(self.focus_part)
                    k = self.view.keypress(size, k)
                    continue

                if self.focus_part == 'footer': # 'Search' mode?
                    if k == 'enter': # exit if single widget in list 
                        widget = self.l_walker.get_widget_if_single()
                        if widget:
                            self.focus_node = widget.node
                            return
                    k = self.view.keypress(size, k)
                    text = self.footer.get_edit_text()
                    self.l_walker.set_filter(text)
                    continue
                elif k in ('q','Q'):
                    print "\033[2J"
                    sys.exit()
                elif k == 'enter':
                    self.focus_node = focus.node
                    return
                k = self.view.keypress(size, k)

class CredsError(Exception):
    pass

class credentials(object):
    def __init__(self, node):
        node = node.firstChild
        self.creds = {}
        while (node):
            if node.nodeName == 'auth':
                a_tag = node.getAttribute('id')
                if not a_tag: 
                    raise CredsError("Credentials: can't get attribute 'line' "
                    "for node '%s'" % a_node.nodeName)
                for a_node in node.childNodes:
                    a_name = a_node.nodeName
                    if a_name not in ('login', 'password', 'authitem'):
                        a_node = a_node.nextSibling
                        continue
                    a_value = a_node.getAttribute('line')
                    if not a_value: 
                        raise CredsError("Credentials: can't get attribute 'line' "
                        "for node '%s'" % a_node.nodeName)
                    self.creds["%%%s/%s%%" % (a_tag, a_name)] = a_value
            node = node.nextSibling

    def __str__(self):
        return "creds:" + join(self.creds)

    def repl_auth(self, str):
        try: return re.sub('%.*?%', lambda x: self.creds[x.group(0)], str)
        except KeyError:
            raise CredsError("Credentials: can't find auth value for '%s'" % str)

class StatementError(Exception):
    pass

class statement(object):
    def __init__(self, spawn, node, creds):
        self.spawnobj = spawn
        self.node = node
        self.creds = creds

    def __find_next_inorder(self, node):
        sib = node
        while True:
            sib = sib.nextSibling
            if not sib: break
            if sib.nodeType != 3: return sib
        parent = node.parentNode
        if parent.nodeName == 'template':
            return None
        else:
            return self.__find_next_inorder(parent)

    def __find_next_inscope(self, node):
        for child in node.childNodes:
            if child.nodeType != 3: return child
        parent = node.parentNode
        if parent.nodeName == 'template':
            return None
        else:
            return self.__find_next_inscope(parent)

    def find_next_inorder(self):
        return self.__find_next_inorder(self.node)

    def find_next_inscope(self):
        return self.__find_next_inscope(self.node)

    def run(self):
        pass

class stmt_ssh(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_ssh, self).__init__(spawn, node, creds)

    def run(self):
        if(self.spawnobj.__class__.__name__ != 'pxssh'):
            raise StatementError("Statement 'ssh': can't do ssh login for non-ssh connection")
        login = self.node.getAttribute("login")
        passwd = self.node.getAttribute("password")
        if not (login and passwd): 
            raise CredsError("Statement 'ssh': can't find attribute 'login' or 'password'")
        self.spawnobj.login(self.spawnobj._host_address, login, passwd)
        next_stmt = self.find_next_inorder()
        return next_stmt

class stmt_if(statement):
    """
        Class for <if> statement.
        Skeleton:
        <if expect='line'>
            <statement>
            ....
            <statement>
        </if>        
    """
    def __init__(self, spawn, node, creds):
        super(stmt_if, self).__init__(spawn, node, creds)

    def run(self):
        expect = self.node.getAttribute("expect")
        if not expect: 
            raise CredsError("Statement 'if': can't find attribute 'expect'")
        idx = self.spawnobj.expect([str(expect), pexpect.EOF, pexpect.TIMEOUT])
        next_stmt = None
        if idx == 0:
            next_stmt = self.find_next_inscope()
        else:
            print "Statement 'if': expect '%s' not found" % expect
            next_stmt = self.find_next_inorder()
        return next_stmt

class stmt_switch(statement):
    """
        Class for <swhitch>...<case> statement.
        Skeleton:
        <switch>
            <case expect="line#1">
                <statement>
                    ....
                <statement>
            </case>
            <case expect="line#2">
                ....
            </case>
            ....
        </switch>
    """
    def __init__(self, spawn, node, creds):
        super(stmt_switch, self).__init__(spawn, node, creds)

    def run(self):
        case_nodes = []
        case_lines = []
        for case in self.node.childNodes:
            if case.nodeName != "case": continue
            case_nodes.append(case)
            case_line = case.getAttribute("expect")
            if not case_line: 
                raise CredsError("Statement 'switch - case': can't find attribute 'expect'")
            case_lines.append(case_line)
            
        idx = self.spawnobj.expect(case_lines + [pexpect.EOF, pexpect.TIMEOUT], timeout = 5)
        next_stmt = None
        try: case_nodes[idx]
        except IndexError:
            print "Statement 'swith': cases '%s' not found" % join (case_lines, ", ")
            next_stmt = self.find_next_inorder()
        else:
            self.node = case_nodes[idx]
            next_stmt = self.find_next_inscope()
        return next_stmt

class stmt_send(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_send, self).__init__(spawn, node, creds)

    def run(self):
        send = self.node.getAttribute("line")
        if not send: 
            raise CredsError("Statement 'send': can't find attribute 'line'")
        self.spawnobj.sendline(self.creds.repl_auth(send))
        next_stmt = self.find_next_inorder()
        return next_stmt

class stmt_prt(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_prt, self).__init__(spawn, node, creds)

    def run(self):
        prt = self.node.getAttribute("line")
        if not prt: 
            raise CredsError("Statement 'print': can't find attribute 'line'")
        print self.creds.repl_auth(prt)
        next_stmt = self.find_next_inorder()
        return next_stmt

class stmt_interact(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_interact, self).__init__(spawn, node, creds)

    def run(self):
        self.spawnobj.logfile_read = None
        self.spawnobj.interact()
        sys.exit()

class stmt_sleep(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_sleep, self).__init__(spawn, node, creds)

    def run(self):
        secs = self.node.getAttribute("secs")
        if not secs: 
            raise CredsError("Statement 'sleep': can't find attribute 'secs'")
        time.sleep(int(secs))
        next_stmt = self.find_next_inorder()
        return next_stmt

class stmt_term(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_term, self).__init__(spawn, node, creds)

    def run(self):
        self.spawnobj.logfile_read = None
        self.spawnobj.terminate()
        sys.exit()

class stmt_noewait(statement):
    def __init__(self, spawn, node, creds):
        super(stmt_noewait, self).__init__(spawn, node, creds)

    def run(self):
        noecho = self.spawnobj.waitnoecho(timeout = 5)
        if not noecho: 
            raise CredsError("Statement 'waitnoecho': can't get NOECHO terminal mode")

        next_stmt = self.find_next_inorder()
        return next_stmt

class template(statement):

    stmt_classes = {
        'if' : stmt_if,
        'send' : stmt_send,
        'print' : stmt_prt,
        'interact' : stmt_interact,
        'sleep' : stmt_sleep,
        'terminate' : stmt_term,
        'waitnoecho' : stmt_noewait,
        'switch' : stmt_switch,
        'ssh' : stmt_ssh
    }

    def __init__(self, spawn, tmpl, auth):
        node = None
        creds = credentials(auth)
        for child in tmpl.childNodes:
            if child.nodeType != 3:
                node = child
                break
        super(template, self).__init__(spawn, node, creds)

    def __iter__(self):
        return self

    def next(self):
        if not self.node: raise StopIteration
        if self.node.nodeName in self.stmt_classes:
            stmt = self.stmt_classes[self.node.nodeName]
            stmt_obj = stmt(self.spawnobj, self.node, self.creds)
            self.node = stmt_obj.run()
            return self
        else:
            self.node = self.find_next_inorder()

    def run(self):
        for stmt_node in self: pass

def find_tag(xmlobj, path):
    """
        Finds XML element in 'xmlobj' by path in 'path'
        Path format similair to XPath ("element1/element2/element3")
        NOTE: XML attributes (XPath's '@attr') does not support
    """
    strarr = path.split('/')
    def recur_find_tag(xmlobj, strarr):
        if len(strarr) == 0:
            return xmlobj
        for n in xmlobj.childNodes:
            if n.nodeName == strarr[0]:
                if len(strarr) == 1:
                    return n
                else:
                    del strarr[0]
                    node = recur_find_tag(n, strarr[0:])
                    if node: return node
            else:
                node = recur_find_tag(n, strarr[0:])
                if node: return node
    return recur_find_tag(xmlobj, strarr)

def find_template(confroot, id):
    """
        Finds <template> by 'id'
        'confroot' points to app's XML config root Document
    """
    tmpls = find_tag(confroot, "config/templates")
    for tmpl in tmpls.childNodes:
        if tmpl.nodeType == 3:
            continue
        if tmpl.getAttribute('id') == id:
            return tmpl

class ConfError(Exception):
    pass

def lib_main(home_config, sys_config):
    home_config = os.path.expanduser(home_config)
    sysconf = minidom.parse(sys_config)
    homeconf = minidom.parse(home_config)
    hosts = find_tag(sysconf, "config/hosts")
    auths = find_tag(homeconf, "config/auths")
    if not hosts:
        raise ConfError("Configuration for 'config/hosts "
            "not found")
    if not auths:
        raise ConfError("Configuration for 'config/auths' "
            "not found")

    print "\033k%s\033\\" % 'Screenex'
    hnode = consoleui(hosts).main()
    print "\033[2J"

    hnode_access = hnode.getElementsByTagName('access')[0]
    hnode_template = hnode.getElementsByTagName('template')[0]

    host_name = hnode.getAttribute('name')
    host_address = hnode_access.getAttribute('address')
    host_proto = hnode_access.getAttribute('protocol')
    host_template = hnode_template.getAttribute('ref')

    spawnobj = 0
    if host_proto == 'telnet':
        spawnobj = pexpect.spawn('telnet ' + host_address)
    elif host_proto == 'ssh':
        spawnobj = pxssh.pxssh()
        spawnobj._host_address = host_address
    else:
        raise ConfError("main: bad protocol for host '%s'" 
            % host_name)

    spawnobj.logfile_read = sys.stdout

    tmpl = find_template(sysconf, host_template)
    if not tmpl:
        raise ConfError("Configuration for template '%s' "
            "not found" % host_template)

    tinst = template(spawnobj, tmpl, auths)

    print "\033k%s\033\\" % host_name

    tinst.run()
