clime
=====

Clang + Sublime Text = Clime. A C++ development bundle for Sublime Text


Features
--------

The current feature set of Clime is modest. See the [Plans](#plans) section below for what features are in the works.

Current features:
   * *Syntax checking*: Clime parses C++ headers/sources using Clang to automatically highlight any syntax issues.

Settings
--------

The following settings can be set in Clime.sublime-settings:

   * *file_extensions*: an array of file extensions Clime should recognize as C++ files. Clime will automatically run on any of the file types specified in the list. Defaults to: [".h", ".hpp", ".cc", ".cpp"]

Plans
-----

The current syntax checking functionality is (we hope) the tip of the iceberg for Clime. The plan is to make it into a much more useful tool for C++ development. The next set of features planned is around indexing of C++ source code in Sublime projects. Features like jumping between method declarations and definitions, finding references to classes/methods and maybe even autocompletion.