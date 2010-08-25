# Copyright (C) 2009, 2010  Roman Zimbelmann <romanz@lavabit.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import _curses

from ranger.shared import FileManagerAware, EnvironmentAware
from ranger.gui.curses_shortcuts import CursesShortcuts

class Displayable(EnvironmentAware, FileManagerAware, CursesShortcuts):
	"""
	Displayables are objects which are displayed on the screen.

	This is just the abstract class, defining basic operations
	such as resizing, printing, changing colors.
	Subclasses of displayable can extend these methods:

	draw() -- draw the object. Is only called if visible.
	poke() -- is called just before draw(), even if not visible.
	finalize() -- called after all objects finished drawing.
	click(event) -- called with a MouseEvent. This is called on all
		visible objects under the mouse, until one returns True.
	press(key) -- called after a key press on focused objects.
	destroy() -- called before destroying the displayable object

	Additionally, there are these methods:

	__contains__(item) -- is the item (y, x) inside the widget?

	These attributes are set:

	Modifiable:
		focused -- Focused objects receive press() calls.
		visible -- Visible objects receive draw() and finalize() calls
		need_redraw -- Should the widget be redrawn? This variable may
			be set at various places in the script and should eventually be
			handled (and unset) in the draw() method.

	Read-Only: (i.e. reccomended not to change manually)
		win -- the own curses window object
		parent -- the parent (DisplayableContainer) object or None
		x, y, wid, hei -- absolute coordinates and boundaries
		settings, fm, env -- inherited shared variables
	"""

	def __init__(self, win, env=None, fm=None, settings=None):
		from ranger.gui.ui import UI
		if env is not None:
			self.env = env
		if fm is not None:
			self.fm = fm
		if settings is not None:
			self.settings = settings

		self.need_redraw = True
		self.focused = False
		self.visible = True
		self.x = 0
		self.y = 0
		self.wid = 0
		self.hei = 0
		self.paryx = (0, 0)
		self.parent = None

		self._old_visible = self.visible

		if win is not None:
			if isinstance(self, UI):
				self.win = win
			else:
				self.win = win.derwin(1, 1, 0, 0)

	def __nonzero__(self):
		"""Always True"""
		return True
	__bool__ = __nonzero__

	def __contains__(self, item):
		"""
		Is item inside the boundaries?
		item can be an iterable like [y, x] or an object with x and y methods.
		"""
		try:
			y, x = item.y, item.x
		except AttributeError:
			try:
				y, x = item
			except (ValueError, TypeError):
				return False

		return self.contains_point(y, x)

	def draw(self):
		"""
		Draw the object. Called on every main iteration if visible.
		Containers should call draw() on their contained objects here.
		Override this!
		"""

	def destroy(self):
		"""
		Called when the object is destroyed.
		Override this!
		"""

	def contains_point(self, y, x):
		"""
		Test whether the point (with absolute coordinates) lies
		within the boundaries of this object.
		"""
		return (x >= self.x and x < self.x + self.wid) and \
				(y >= self.y and y < self.y + self.hei)

	def click(self, event):
		"""
		Called when a mouse key is pressed and self.focused is True.
		Override this!
		"""
		pass

	def press(self, key):
		"""
		Called when a key is pressed and self.focused is True.
		Override this!
		"""
		pass

	def poke(self):
		"""Called before drawing, even if invisible"""
		if self._old_visible != self.visible:
			self._old_visible = self.visible
			self.need_redraw = True

			if not self.visible:
				self.win.erase()

	def finalize(self):
		"""
		Called after every displayable is done drawing.
		Override this!
		"""
		pass

	def resize(self, y, x, hei=None, wid=None):
		"""Resize the widget"""
		do_move = True
		try:
			maxy, maxx = self.env.termsize
		except TypeError:
			pass
		else:
			if hei is None:
				hei = maxy - y

			if wid is None:
				wid = maxx - x

			if x < 0 or y < 0:
				raise ValueError("Starting point below zero!")

			#if wid < 1 or hei < 1:
			#	raise OutOfBoundsException("WID and HEI must be >=1!")

			if x + wid > maxx and y + hei > maxy:
				raise ValueError("X and Y out of bounds!")

			if x + wid > maxx:
				raise ValueError("X out of bounds!")

			if y + hei > maxy:
				raise ValueError("Y out of bounds!")

		window_is_cleared = False

		if hei != self.hei or wid != self.wid:
			#log("resizing " + str(self))
			self.win.erase()
			self.need_redraw = True
			window_is_cleared = True
			try:
				self.win.resize(hei, wid)
			except:
				# Not enough space for resizing...
				try:
					self.win.mvderwin(0, 0)
					do_move = True
					self.win.resize(hei, wid)
				except:
					pass
					#raise ValueError("Resizing Failed!")

			self.hei, self.wid = self.win.getmaxyx()

		if do_move or y != self.paryx[0] or x != self.paryx[1]:
			if not window_is_cleared:
				self.win.erase()
				self.need_redraw = True
			#log("moving " + str(self))
			try:
				self.win.mvderwin(y, x)
			except:
				pass

			self.paryx = self.win.getparyx()
			self.y, self.x = self.paryx
			if self.parent:
				self.y += self.parent.y
				self.x += self.parent.x

	def __str__(self):
		return self.__class__.__name__

class DisplayableContainer(Displayable):
	"""
	DisplayableContainers are Displayables which contain other Displayables.

	This is also an abstract class. The methods draw, poke, finalize,
	click, press and destroy are extended here and will recursively
	call the function on all contained objects.

	New methods:

	add_child(object) -- add the object to the container.
	remove_child(object) -- remove the object from the container.

	New attributes:

	container -- a list with all contained objects (rw)
	"""

	def __init__(self, win, env=None, fm=None, settings=None):
		if env is not None:
			self.env = env
		if fm is not None:
			self.fm = fm
		if settings is not None:
			self.settings = settings

		self.container = []

		Displayable.__init__(self, win)

	# ------------------------------------ extended or overidden methods

	def poke(self):
		"""Recursively called on objects in container"""
		Displayable.poke(self)
		for displayable in self.container:
			displayable.poke()

	def draw(self):
		"""Recursively called on visible objects in container"""
		for displayable in self.container:
			if self.need_redraw:
				displayable.need_redraw = True
			if displayable.visible:
				displayable.draw()

		self.need_redraw = False

	def finalize(self):
		"""Recursively called on visible objects in container"""
		for displayable in self.container:
			if displayable.visible:
				displayable.finalize()

	def press(self, key):
		"""Recursively called on objects in container"""
		focused_obj = self._get_focused_obj()

		if focused_obj:
			focused_obj.press(key)
			return True
		return False

	def click(self, event):
		"""Recursively called on objects in container"""
		focused_obj = self._get_focused_obj()
		if focused_obj and focused_obj.click(event):
			return True

		for displayable in self.container:
			if displayable.visible and event in displayable:
				if displayable.click(event):
					return True

		return False

	def destroy(self):
		"""Recursively called on objects in container"""
		for displayable in self.container:
			displayable.destroy()

	# ----------------------------------------------- new methods

	def add_child(self, obj):
		"""Add the objects to the container."""
		if obj.parent:
			obj.parent.remove_child(obj)
		self.container.append(obj)
		obj.parent = self

	def remove_child(self, obj):
		"""Remove the object from the container."""
		try:
			self.container.remove(obj)
		except ValueError:
			pass
		else:
			obj.parent = None

	def _get_focused_obj(self):
		# Finds a focused displayable object in the container.
		for displayable in self.container:
			if displayable.focused:
				return displayable
			try:
				obj = displayable._get_focused_obj()
			except AttributeError:
				pass
			else:
				if obj is not None:
					return obj
		return None