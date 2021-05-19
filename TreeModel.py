# -*- coding: utf-8 -*-

try:
    from PySide import QtCore
    from PySide import QtGui
    from PySide import QtWidgets
except:
    from PyQt5.QtCore import pyqtSlot as Slot
    from PyQt5 import QtCore
    from PyQt5 import QtGui
    from PyQt5 import QtWidgets

import ItemProperty as iprop

import logging
logger = logging.getLogger("PySel.TreeModel")

# https://doc.qt.io/qt-5/qtwidgets-itemviews-simpletreemodel-example.html


class TreeItem:
    def __init__(self, data = [], isfolder = False, parent = None):
        self._parentItem = parent
        self._itemData = data
        self._childItems = []
        self._checkedItemsCount = 0
        self._checkedPartiallyCount = 0
        self._checkstate = QtCore.Qt.Unchecked
        self._changed = False
        self._initcheckstate = None
        self.syncstate = None
        self.isfolder = isfolder
        self.isinvalid = False

    def appendChild(self, child):
        if isinstance(child, TreeItem):
            logger.debug("appendChild {}".format(child.data(0)))
            self._childItems.append(child)
            if child.getCheckState() == QtCore.Qt.Checked:
                self._checkedItemsCount += 1
            if child.getCheckState() == QtCore.Qt.PartiallyChecked:
                self._checkedPartiallyCount += 1
        else:
            raise TypeError('Child\'s type is {0}, but must be TreeItem'.format(str(type(child))))

    def child(self, row):
        if row < -len(self._childItems) or row >= len(self._childItems):
            return None
        return self._childItems[row]

    def childCount(self):
        return len(self._childItems)

    def childRemoteCount(self):
        loccnt = 0
        for ch in self._childItems:
            if ch.syncstate is iprop.SyncState.newlocal:
                loccnt += 1
        return len(self._childItems) - loccnt

    def childNames(self):
        rv = []
        for ch in self._childItems:
            rv.append(ch._itemData[0])
        return rv
    
    def columnCount(self):
        return len(self._itemData)

    def data(self, column):
        if column < -len(self._itemData) or column >= len(self._itemData):
            return None
        return self._itemData[column]
    
    def setData(self, column, value):
        if column < -len(self._itemData) or column >= len(self._itemData):
            return False
        self._itemData[column] = value
        return True

    def setCheckState(self, st):
        if st != self._checkstate and \
                self._parentItem is not None and \
                self in self._parentItem._childItems:
            if st == QtCore.Qt.Checked:
                logger.info("Entry \'{0}\' is checked".format(self._itemData[0]))
                self._parentItem._checkedItemsCount += 1
                if self._checkstate == QtCore.Qt.PartiallyChecked:
                    self._parentItem._checkedPartiallyCount -= 1
            elif st == QtCore.Qt.PartiallyChecked:
                logger.info("Entry \'{0}\' is partially checked".format(self._itemData[0]))
                self._parentItem._checkedPartiallyCount += 1
                if self._checkstate == QtCore.Qt.Checked:
                    self._parentItem._checkedItemsCount -= 1
            else:
                logger.info("Entry \'{0}\' is unchecked".format(self._itemData[0]))
                if self._checkstate == QtCore.Qt.Checked:
                    self._parentItem._checkedItemsCount -= 1
                else:
                    self._parentItem._checkedPartiallyCount -= 1
            self._checkstate = st

    def getCheckState(self):
        return self._checkstate

    def setSyncState(self, v):
        if not isinstance(v, iprop.SyncState):
            raise TypeError('State\'s type is {0}, but must be ItemProperty.SyncState'.format(str(type(v))))
        self.syncstate = v

    def getSyncState(self):
        return self.syncstate

    def setChanged(self):
        'In the model should be called *before* set actual state'
        if self._initcheckstate is None:
            self._initcheckstate = self._checkstate
        self._changed = True

    def isChanged(self):
        if self._changed:
            # False if changed but returned back
            return True if self._initcheckstate != self._checkstate else False 
        return False

    def setInvalid(self, v=True):
        self.isinvalid = v

    def updateCheckState(self):
        '''
        compare checked count with child count and return True if checkstate was changed, 
        the parent state also must be updated in this case
        '''
        if self._checkedItemsCount == 0 and self._checkedPartiallyCount == 0:
            self.setCheckState(QtCore.Qt.Unchecked)
            return True
        
        elif self.childRemoteCount() != self._checkedItemsCount:
            self.setCheckState(QtCore.Qt.PartiallyChecked)
            return True

        elif self.childRemoteCount() == self._checkedItemsCount:
            self.setCheckState(QtCore.Qt.Checked)
            return True

        return False
    
    def row(self):
        if self._parentItem is not None:
            return self._parentItem._childItems.index(self)
        return 0
    
    def parentItem(self):
        return self._parentItem

    def toDict(self):
        item = {}
        item['size'] = self._itemData[1]
        item['modified'] = self._itemData[2].toString(QtCore.Qt.ISODate)
        item['type'] = iprop.Type.DIRECTORY.name if self.isfolder \
                            else iprop.Type.FILE.name
        item['syncstate'] = self.syncstate.name
        item['children'] = len(self._childItems)
        return item


class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self, data = [], parent = None):
        QtCore.QAbstractItemModel.__init__(self, parent)
        self._tv = parent
        self._rootItem = TreeItem(['Title', 'Size', 'Modified'])
        self._changedList = []
        self._appStyle = QtWidgets.QApplication.style()
        self._setupModelData(data, self._rootItem)

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item is not None:
                return item

        return self._rootItem

    def data(self, index, role):
        if not isinstance(index, QtCore.QModelIndex):
            raise TypeError('Index\'s type is {0}, but must be QModelIndex'.format(str(type(index))))
        if not index.isValid():
            return None

        item = index.internalPointer()
        
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            return item.getCheckState()
        
        if role == QtCore.Qt.DecorationRole and index.column() == 0:
            if item.isfolder:
                if self._tv.isExpanded(index):
                    return self._appStyle.standardIcon(QtWidgets.QStyle.SP_DirOpenIcon)
                else:
                    return self._appStyle.standardIcon(QtWidgets.QStyle.SP_DirIcon)
            else:
                return self._appStyle.standardIcon(QtWidgets.QStyle.SP_FileIcon)

        # set colors in depends of sync state
        if role == QtCore.Qt.ForegroundRole:
            if item.syncstate is None:
                if item.getCheckState() == QtCore.Qt.Unchecked:
                    return QtGui.QBrush(QtCore.Qt.gray)
            else:
                if item.syncstate is iprop.SyncState.newlocal:
                    return QtGui.QBrush(QtCore.Qt.darkGreen)
                elif item.syncstate is iprop.SyncState.ignored:
                    return QtGui.QBrush(QtCore.Qt.gray)
                elif item.syncstate is iprop.SyncState.conflict:
                    return QtGui.QBrush(QtCore.Qt.red)
                elif item.syncstate is iprop.SyncState.exists:
                    return QtGui.QBrush(QtCore.Qt.blue)
                else:
                    pass

        if role == QtCore.Qt.BackgroundRole:
            if item.isinvalid:
                return QtGui.QBrush(QtCore.Qt.darkRed)

        if role != QtCore.Qt.DisplayRole:
            return None
        
        return item.data(index.column())
    
    def setData(self, index, value, role = QtCore.Qt.EditRole):
        logger.debug("setData value {}".format(value))
        if index.column() == 0:
            if role == QtCore.Qt.CheckStateRole:
                item = self.getItem(index)
                item.setChanged()
                item.setCheckState(value)
                self._addToChangedList(item)
                self.dataChanged.emit(index, index)
                # update parents
                index = self.parent(index)
                while index.isValid():
                    item = self.getItem(index)
                    if not item.updateCheckState():
                        break
                    self._addToChangedList(item)
                    self.dataChanged.emit(index, index)
                    index = self.parent(index)
                return True
            else:
                return False

        return super().setData(index, value, role)

    def _addToChangedList(self, item):
        fn = "/" + self.fullItemName(item)
        if not fn in self._changedList:
            self._changedList.append(fn)
        #elif fn in self._changedList:
        #    self._changedList.remove(fn)

    def flags(self, index):
        if not isinstance(index, QtCore.QModelIndex):
            raise TypeError('Index\'s type is {0}, but must be QModelIndex'.format(str(type(index))))
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        # Qt::ItemIsUserTristate TODO for dirs

        rv = super().flags(index)
        if index.column() == 0:
            rv |= QtCore.Qt.ItemIsUserCheckable
        return rv

    def headerData(self, section, orientation, role = QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._rootItem.data(section);
        return None
    
    def index(self, row, column, parent = QtCore.QModelIndex()):
        if not isinstance(parent, QtCore.QModelIndex):
            raise TypeError('Parent\'s type is {0}, but must be QModelIndex'.format(str(type(parent))))
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
             parentItem = self._rootItem
        else:
             parentItem = self.getItem(parent)

        childItem = parentItem.child(row)
        if childItem is not None:
            return self.createIndex(row, column, childItem);
        return QtCore.QModelIndex();

    def parent(self, index):
        if not isinstance(index, QtCore.QModelIndex):
            raise TypeError('Index\'s type is {0}, but must be QModelIndex'.format(str(type(index))))
        if not index.isValid():
            return QtCore.QModelIndex();

        parentItem = self.getItem(index).parentItem()

        if parentItem is self._rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)
    
    def rowCount(self, parent = QtCore.QModelIndex()):
        if not isinstance(parent, QtCore.QModelIndex):
            raise TypeError('Parent\'s type is {0}, but must be QModelIndex'.format(str(type(parent))))
        if parent.column() > 0:
            return 0;
        
        if not parent.isValid():
             parentItem = self._rootItem
        else:
             parentItem = self.getItem(parent)

        return parentItem.childCount()

    def columnCount(self, parent = QtCore.QModelIndex()):
        if not isinstance(parent, QtCore.QModelIndex):
            raise TypeError('Parent\'s type is {0}, but must be QModelIndex'.format(str(type(parent))))
        if parent.isValid():
            return self.getItem(parent).columnCount()
        return self._rootItem.columnCount()

    def fullItemName(self, item):
        if not isinstance(item, TreeItem):
            raise TypeError('Index\'s type is {0}, but must be TreeItem'.format(str(type(item))))

        if item is self._rootItem:
            return ""

        fin = item.data(0)
        item = item.parentItem()
        while item is not self._rootItem:
            fin = item.data(0) + '/' + fin
            item = item.parentItem()
        return fin

    def rowNamesList(self, index):
        if not isinstance(index, QtCore.QModelIndex):
            raise TypeError('Index\'s type is {0}, but must be QModelIndex'.format(str(type(index))))
        rv = []
        for ch in self.getItem(index)._childItems:
            rv.append({\
                    'name': ch._itemData[0], \
                    'type': iprop.Type.DIRECTORY.name if ch.isfolder else iprop.Type.FILE.name, \
                    'syncstate': iprop.SyncState.unknown if ch.syncstate is None else ch.syncstate, \
                    'children': list(map(lambda x: {'name': x} , ch.childNames()))})
        return rv

    def _fillItemByDict(self, ch, v):
        logger.debug("_fillItemByDict {}".format(v))
        ch._itemData = [
                v['name'], 
                v['size'] if ('size' in v and v['size'] != 0) else None, 
                v['modified'] if 'modified' in v else None,
            ]
        ignored = v['ignored'] if 'ignored' in v else True
        partial = v['partial'] if 'partial' in v else False
        ch.setCheckState(
                QtCore.Qt.PartiallyChecked if partial else
                QtCore.Qt.Checked if not ignored else
                QtCore.Qt.Unchecked)
        if 'syncstate' in v:
            ch.setSyncState(v['syncstate'])
        elif partial or not ignored:
            ch.setSyncState(iprop.SyncState.syncing)
        else:
            ch.setSyncState(iprop.SyncState.ignored)
        if 'invalid' in v and not ignored:
            ch.setInvalid(v['invalid'])
        return ch

    def _setupModelData(self, data, parent=None, _isrecursive=False):
        logger.debug("_setupModelData _isrecursive {}".format(_isrecursive))
        if parent is None:
            parent = self._rootItem
        if not isinstance(parent, TreeItem):
            msg = 'Parent\'s type is {0}, but must be TreeItem'.format(str(type(parent)))
            raise TypeError(msg)
        if not isinstance(data, list):
            msg = 'data\'s type is {0}, but must be list'.format(str(type(data)))
            raise TypeError(msg)
        
        for v in data:
            if parent is self._rootItem and v['name'] == '.stignoreglobal': #additional ignore list may be needed
                continue

            ch = TreeItem([v['name'], None, None], iprop.Type[v['type']] is iprop.Type.DIRECTORY, parent)
            parent.appendChild(ch)
            if _isrecursive:
                continue
            
            self._fillItemByDict(ch, v)
            
            if iprop.Type[v['type']] is iprop.Type.DIRECTORY:
                self._setupModelData(v['children'], ch, _isrecursive=True)

    def updateSubSection(self, index, data):
        logger.debug("updateSubSection at the row {}".format(index.row()))
        if not isinstance(index, QtCore.QModelIndex):
            raise TypeError('Index\'s type is {0}, but must be QModelIndex'.format(str(type(index))))
        if not isinstance(data, list):
            raise TypeError('data\'s type is {0}, but must be list'.format(str(type(data))))
        
        isparentchecked = True if self.getItem(index).getCheckState() == QtCore.Qt.Checked else False
        # use names with string type as python cannot compare items directly
        chnotfoundnames = self.getItem(index).childNames()[:]
        # works well as data does not const complex objects
        newdata = data[:]
        for ch in self.getItem(index)._childItems:
            for v in data:  # TODO should be dict of dicts to avoid second for
                if ch._itemData[0] == v['name']:
                    self._fillItemByDict(ch, v)
                    chnotfoundnames.remove(ch._itemData[0])
                    newdata.remove(v)
                    if isparentchecked:
                        ch.setChanged()
                        self._addToChangedList(ch)

                    if iprop.Type[v['type']] is iprop.Type.DIRECTORY and len(v['children']) != ch.childCount():
                        self.beginInsertRows(index, 0, len(v['children']))
                        self._setupModelData(v['children'], ch, _isrecursive=True)
                        self.endInsertRows()

        # remove unnecessary items
        chlist = self.getItem(index)._childItems  # result is the the link orig, use it later!
        for nametorm in chnotfoundnames:
            for i in range(len(chlist)):
                if nametorm == chlist[i]._itemData[0]:
                    self.beginRemoveRows(index, i, i+1)
                    del chlist[i]
                    self.endRemoveRows()
                    break

        # add new items
        self.beginInsertRows(index, 0, len(newdata))
        self._setupModelData(newdata, self.getItem(index))
        self.endInsertRows()

        # update view
        self.getItem(index).updateCheckState()
        super().dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
        
        indfirst = self.index(0, 0, index)
        indlast = self.index(self.rowCount(index), self.columnCount(index), index)
        super().dataChanged.emit(indfirst, indlast, [QtCore.Qt.DisplayRole])
        
    def checkedStatePathList(self, plist = None, parent = None, pref = '/', state = QtCore.Qt.Checked):
        if plist is None:
            plist = []
        if parent is None:
            parent = self._rootItem
        for item in parent._childItems:
            if pref == '/' and item.data(0) == '.stignoreglobal': #additional ignore list may be needed
                continue
            if item.getCheckState() == state:
                plist.append(pref + item.data(0))
            if (state != QtCore.Qt.Checked) or (item.getCheckState() != QtCore.Qt.Checked) and (item.childCount() > 0):
                self.checkedStatePathList(plist, item, pref + item.data(0) + '/', state)
        return plist
    
    def changedPathList(self, plist = None, parent = None, pref = '/'):
        return self._changedList



