# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""License text templates for plugin scaffolding.

Stores full license bodies keyed by SPDX identifier with
year/author placeholders for substitution at render time.
"""

import re

from shared.spdx import NON_SPDX_PLACEHOLDERS


LICENSES = {
    "MIT": (
        "MIT License\n"
        "\n"
        "Copyright (c) {year} {author_name}\n"
        "\n"
        "Permission is hereby granted, free of charge, "
        "to any person obtaining a copy\n"
        'of this software and associated documentation '
        'files (the "Software"), to deal\n'
        "in the Software without restriction, including "
        "without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute"
        ", sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to"
        " whom the Software is\n"
        "furnished to do so, subject to the following "
        "conditions:\n"
        "\n"
        "The above copyright notice and this permission "
        "notice shall be included in all\n"
        "copies or substantial portions of the "
        "Software.\n"
        "\n"
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT '
        "WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE "
        "WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND "
        "NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY "
        "CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, "
        "TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR "
        "THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n"
    ),
    "Apache-2.0": (
        "                                 Apache License\n"
        "                           Version 2.0, "
        "January 2004\n"
        "                        "
        "http://www.apache.org/licenses/\n"
        "\n"
        "   Copyright {year} {author_name}\n"
        "\n"
        "   Licensed under the Apache License, "
        'Version 2.0 (the "License");\n'
        "   you may not use this file except in "
        "compliance with the License.\n"
        "   You may obtain a copy of the License at\n"
        "\n"
        "       "
        "http://www.apache.org/licenses/LICENSE-2.0\n"
        "\n"
        "   Unless required by applicable law or agreed "
        "to in writing, software\n"
        '   distributed under the License is distributed '
        'on an "AS IS" BASIS,\n'
        "   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND"
        ", either express or implied.\n"
        "   See the License for the specific language "
        "governing permissions and\n"
        "   limitations under the License.\n"
    ),
    "ISC": (
        "ISC License\n"
        "\n"
        "Copyright (c) {year} {author_name}\n"
        "\n"
        "Permission to use, copy, modify, and/or "
        "distribute this software for any\n"
        "purpose with or without fee is hereby granted, "
        "provided that the above\n"
        "copyright notice and this permission notice "
        "appear in all copies.\n"
        "\n"
        'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR '
        "DISCLAIMS ALL WARRANTIES WITH\n"
        "REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED "
        "WARRANTIES OF MERCHANTABILITY\n"
        "AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE "
        "LIABLE FOR ANY SPECIAL, DIRECT,\n"
        "INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY "
        "DAMAGES WHATSOEVER RESULTING FROM\n"
        "LOSS OF USE, DATA OR PROFITS, WHETHER IN AN "
        "ACTION OF CONTRACT, NEGLIGENCE OR\n"
        "OTHER TORTIOUS ACTION, ARISING OUT OF OR IN "
        "CONNECTION WITH THE USE OR\n"
        "PERFORMANCE OF THIS SOFTWARE.\n"
    ),
    "GPL-3.0": (
        "                    GNU GENERAL PUBLIC LICENSE\n"
        "                       Version 3, "
        "29 June 2007\n"
        "\n"
        " Copyright (C) {year} {author_name}\n"
        "\n"
        " This program is free software: you can "
        "redistribute it and/or modify\n"
        " it under the terms of the GNU General Public "
        "License as published by\n"
        " the Free Software Foundation, either version 3 "
        "of the License, or\n"
        " (at your option) any later version.\n"
        "\n"
        " This program is distributed in the hope that "
        "it will be useful,\n"
        " but WITHOUT ANY WARRANTY; without even the "
        "implied warranty of\n"
        " MERCHANTABILITY or FITNESS FOR A PARTICULAR "
        "PURPOSE.  See the\n"
        " GNU General Public License for more details.\n"
        "\n"
        " You should have received a copy of the GNU "
        "General Public License\n"
        " along with this program.  If not, see "
        "<https://www.gnu.org/licenses/>.\n"
    ),
    "AGPL-3.0": (
        "                    GNU AFFERO GENERAL PUBLIC "
        "LICENSE\n"
        "                       Version 3, "
        "19 November 2007\n"
        "\n"
        " Copyright (C) {year} {author_name}\n"
        "\n"
        " This program is free software: you can "
        "redistribute it and/or modify\n"
        " it under the terms of the GNU Affero General "
        "Public License as published by\n"
        " the Free Software Foundation, either version 3 "
        "of the License, or\n"
        " (at your option) any later version.\n"
        "\n"
        " This program is distributed in the hope that "
        "it will be useful,\n"
        " but WITHOUT ANY WARRANTY; without even the "
        "implied warranty of\n"
        " MERCHANTABILITY or FITNESS FOR A PARTICULAR "
        "PURPOSE.  See the\n"
        " GNU Affero General Public License for "
        "more details.\n"
        "\n"
        " You should have received a copy of the GNU "
        "Affero General Public License\n"
        " along with this program.  If not, see "
        "<https://www.gnu.org/licenses/>.\n"
    ),
    "UNLICENSED": (
        "Copyright (c) {year} {author_name}\n"
        "\n"
        "All rights reserved. No part of this software "
        "may be reproduced,\n"
        "distributed, or transmitted in any form or by "
        "any means without the\n"
        "prior written permission of the copyright "
        "holder.\n"
    ),
}

SUPPORTED_LICENSES = list(LICENSES.keys())

# Curated short list shown in the interactive scaffold prompt.
# Capped at 4 to fit AskUserQuestion's option cap (#85 family). Other
# ids in LICENSES (ISC, AGPL-3.0) remain accepted by validation for
# non-interactive callers; arbitrary SPDX ids reach a placeholder
# LICENSE via the "Other" branch in get_license_text.
PROMPT_LICENSE_OPTIONS = [
    "MIT",
    "Apache-2.0",
    "GPL-3.0",
    "UNLICENSED",
]

# Loose SPDX identifier shape — letters / digits / dot / plus / dash.
# Accepts obscure-but-real ids like ``GPL-3.0-only``, ``LGPL-3.0-or-later``,
# ``0BSD``, ``MPL-2.0``. The deny-list lives in ``shared.spdx`` (UNLICENSED,
# Proprietary, None, TBD, ...) and runs separately — those are valid
# *values* here but get attribution-only treatment downstream.
_SPDX_LICENSE_ID_RE = re.compile(r"^[A-Za-z0-9.+\-]+$")


def is_valid_license_id(license_id: str) -> bool:
    """Return True if ``license_id`` is acceptable for scaffolding.

    Accepts:
      - Any id known in ``LICENSES`` (full text available)
      - Any placeholder in ``NON_SPDX_PLACEHOLDERS`` (UNLICENSED-style)
      - Any string matching the loose SPDX shape — for those we write
        a placeholder LICENSE and rely on ``reuse lint`` downstream
        to catch typos

    Rejects empty strings and strings with whitespace / shell
    metacharacters / control chars.
    """
    if not license_id or not license_id.strip():
        return False
    if license_id in LICENSES or license_id in NON_SPDX_PLACEHOLDERS:
        return True
    return bool(_SPDX_LICENSE_ID_RE.match(license_id))


def get_license_text(
    license_id: str, year: str, author_name: str
) -> str:
    """Get rendered license text for a given SPDX identifier.

    Behavior:
      - If ``license_id`` is in ``LICENSES``: returns the full known
        text with ``{year}`` and ``{author_name}`` substituted
      - If ``license_id`` is in ``NON_SPDX_PLACEHOLDERS`` (UNLICENSED,
        Proprietary, ...): returns the UNLICENSED-style attribution
        block (proprietary, all-rights-reserved)
      - Otherwise (any other valid-looking SPDX id): returns a
        placeholder LICENSE that names the id and asks the author to
        paste in the canonical text. ``reuse lint`` will surface
        typos in the id itself.

    Args:
        license_id: SPDX license identifier
        year: Copyright year
        author_name: Author/copyright holder name

    Returns:
        Full LICENSE file contents

    Raises:
        ValueError: If ``license_id`` is empty or fails the loose
            SPDX format check (see ``is_valid_license_id``)
    """
    if not is_valid_license_id(license_id):
        raise ValueError(
            f"Invalid license identifier: {license_id!r}. "
            f"Expected an SPDX id (e.g., 'MIT', 'MPL-2.0', "
            f"'Apache-2.0') or a recognized placeholder "
            f"('UNLICENSED', 'Proprietary')."
        )

    if license_id in LICENSES:
        text = LICENSES[license_id]
    elif license_id in NON_SPDX_PLACEHOLDERS:
        # Treat all proprietary / placeholder ids uniformly with the
        # UNLICENSED template.
        text = LICENSES["UNLICENSED"]
    else:
        # Custom / unknown SPDX id picked via "Other". Emit a
        # minimal LICENSE shell so the project still has *something*
        # at the root and consumers know what to look for.
        text = (
            "{license_id}\n"
            "\n"
            "Copyright (c) {year} {author_name}\n"
            "\n"
            "This project is licensed under the {license_id} "
            "license. The full text of this license is not "
            "bundled in the scaffold — paste the canonical text "
            "from https://spdx.org/licenses/{license_id}.html "
            "here, or use `curl` against the SPDX license list "
            "to fetch it.\n"
        )

    text = text.replace("{license_id}", license_id)
    text = text.replace("{year}", year)
    text = text.replace("{author_name}", author_name)
    return text
