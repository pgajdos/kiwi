# Copyright (c) 2015 SUSE Linux GmbH.  All rights reserved.
#
# This file is part of kiwi.
#
# kiwi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# kiwi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with kiwi.  If not, see <http://www.gnu.org/licenses/>
#
from lxml import etree
from tempfile import NamedTemporaryFile
import os
from six import BytesIO
from builtins import bytes

# project
from .defaults import Defaults
from . import xml_parse

from .exceptions import (
    KiwiSchemaImportError,
    KiwiValidationError,
    KiwiDescriptionInvalid,
    KiwiDataStructureError,
    KiwiDescriptionConflict
)


class XMLDescription(object):
    """
    Implements data management for the XML description

    * XSLT Style Sheet processing to apply on this version of kiwi
    * Schema Validation based on RelaxNG schema
    * Loading XML data into internal data structures

    Attributes

    * :attr:`description_xslt_processed`
        XML data after xsltproc processing

    * :attr:`description`
        path to XML description file

    * :attr:`derived_from`
        path to base XML description file

    * :attr:`xml_content`
        XML description data as content string
    """
    def __init__(self, description=None, derived_from=None, xml_content=None):
        if description and xml_content:
            raise KiwiDescriptionConflict(
                'description and xml_content are mutually exclusive'
            )
        self.description_xslt_processed = NamedTemporaryFile()
        self.derived_from = derived_from

        self.description = description
        self.xml_content = xml_content

    def load(self):
        """
        Read XML description, pass it along to the XSLT processor,
        validate it against the schema and finally pass it to the
        autogenerated(generateDS) parser.

        :return: instance of XML toplevel domain (image)
        :rtype: object
        """
        self._xsltproc()
        try:
            relaxng = etree.RelaxNG(
                etree.parse(Defaults.get_schema_file())
            )
        except Exception as e:
            raise KiwiSchemaImportError(
                '%s: %s' % (type(e).__name__, format(e))
            )
        try:
            description = etree.parse(self.description_xslt_processed.name)
            validation_ok = relaxng.validate(
                description
            )
        except Exception as e:
            raise KiwiValidationError(
                '%s: %s' % (type(e).__name__, format(e))
            )
        if not validation_ok:
            if self.description:
                message = 'Schema validation for {description} failed'.format(
                    description=self.description
                )
            else:
                message = 'Schema validation for XML content failed'
            raise KiwiDescriptionInvalid(message)
        return self.__parse()

    def __parse(self):
        try:
            parse = xml_parse.parse(
                self.description_xslt_processed.name, True
            )
            parse.description_dir = self.description and os.path.dirname(
                self.description
            )
            parse.derived_description_dir = self.derived_from
            return parse
        except Exception as e:
            raise KiwiDataStructureError(
                '%s: %s' % (type(e).__name__, format(e))
            )

    def _xsltproc(self):
        """
        Apply XSLT style sheet rules to the XML data

        The result of the XSLT processing is stored in a named
        temporary file and used for further schema validation
        and parsing into the data structure classes
        """
        xslt_transform = etree.XSLT(
            etree.parse(Defaults.get_xsl_stylesheet_file())
        )

        xml_source = self.description if self.description else \
            BytesIO(bytes(self.xml_content))

        with open(self.description_xslt_processed.name, "wb") as xsltout:
            xsltout.write(
                etree.tostring(xslt_transform(etree.parse(xml_source)))
            )
