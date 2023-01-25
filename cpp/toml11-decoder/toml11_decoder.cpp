/*
 * toml11_decoder
 *
 * Parse a TOML document and output data as tagged JSON in the format
 * expected by https://github.com/BurntSushi/toml-test
 *
 * This code is based on
 *   https://github.com/ToruNiina/toml11/blob/master/tests/check_toml_test.cpp
 *   written by Toru Niina.
 *
 * Modified by Joris van Rantwijk:
 *  - Implement independent JSON serialization that does not rely on
 *    the toml11 TOML serializer.
 *  - Correctly escape control characters in JSON strings.
 */

#include <cmath>
#include <iomanip>
#include <iostream>

#include <toml.hpp>


struct tagged_json_serializer
{
    tagged_json_serializer(std::ostream& os)
      : os_(os)
    { }

    void operator()(toml::boolean v)
    {
        write_value("bool", v ? "true" : "false");
    }

    void operator()(toml::integer v)
    {
        write_value("integer", std::to_string(v));
    }

    void operator()(toml::floating v)
    {
        if (std::isnan(v))
        {
            write_value("float", "nan");
        }
        else if (!std::isfinite(v))
        {
            write_value("float", std::signbit(v) ? "-inf" : "inf");
        }
        else
        {
            std::stringstream ss;
            ss << std::setprecision(18) << v;
            write_value("float", ss.str());
        }
    }

    void operator()(const toml::string& v)
    {
        write_value("string", v.str);
    }

    void operator()(const toml::local_time& v)
    {
        write_value("time-local", format_datetime(v));
    }

    void operator()(const toml::local_date& v)
    {
        write_value("date-local", format_datetime(v));
    }

    void operator()(const toml::local_datetime& v)
    {
        write_value("datetime-local", format_datetime(v));
    }

    void operator()(const toml::offset_datetime& v)
    {
        write_value("datetime", format_datetime(v));
    }

    void operator()(const toml::array& v)
    {
        os_ << '[';
        bool is_first = true;
        for (const auto& elem : v)
        {
            if (!is_first)
            {
                os_ << ',';
            }
            is_first = false;
            toml::visit(*this, elem);
        }
        os_ << ']';
    }

    void operator()(const toml::table& v)
    {
        os_ << '{';
        bool is_first = true;
        for (const auto& elem : v)
        {
            if (!is_first)
            {
                std::cout << ',';;
            }
            is_first = false;
            os_ << format_string(elem.first);
            os_ << ':';
            toml::visit(*this, elem.second);
        }
        os_ << '}';
    }

  private:

    std::string format_datetime(const toml::local_time& v)
    {
        int hour = v.hour, minute = v.minute, second = v.second;
        int usec = 1000 * v.millisecond + v.microsecond;
        std::stringstream ss;
        ss  << std::setfill('0')
            << std::setw(2) << hour
            << std::setw(1) << ':'
            << std::setw(2) << minute
            << std::setw(1) << ':'
            << std::setw(2) << second;
        if (usec != 0)
        {
            ss << std::setw(1) << '.'
               << std::setw(6) << usec;
        }
        return ss.str();
    }

    std::string format_datetime(const toml::local_date& v)
    {
        int year = v.year, month = v.month + 1, day = v.day;
        std::stringstream ss;
        ss  << std::setfill('0')
            << std::setw(4) << year
            << std::setw(1) << '-'
            << std::setw(2) << month
            << std::setw(1) << '-'
            << std::setw(2) << day;
        return ss.str();
    }

    std::string format_datetime(const toml::local_datetime& v)
    {
        return format_datetime(v.date) + "T" + format_datetime(v.time);
    }

    std::string format_datetime(const toml::offset_datetime& v)
    {
        std::stringstream ss;
        int offset_minutes = 60 * v.offset.hour + v.offset.minute;
        ss << format_datetime(v.date)
           << 'T'
           << format_datetime(v.time)
           << (offset_minutes < 0 ? '-' : '+')
           << std::setfill('0')
           << std::setw(2) << (std::abs(offset_minutes) / 60)
           << std::setw(1) << ':'
           << std::setw(2) << (std::abs(offset_minutes) % 60);
        return ss.str();
    }

    std::string format_escaped_unicode(unsigned int codepoint)
    {
        std::stringstream ss;
        if (codepoint < 0x10000)
        {
            ss << "\\u";
            ss << std::hex << std::setfill('0') << std::setw(4) << codepoint;
        }
	else
        {
            unsigned int code1 = 0xd800 + ((codepoint - 0x10000) >> 10);
            unsigned int code2 = 0xdc00 + (codepoint & 0x3ff);
            ss << "\\u";
            ss << std::hex << std::setfill('0') << std::setw(4) << code1;
            ss << std::setw(1) << "\\u";
            ss << std::hex << std::setfill('0') << std::setw(4) << code2;
        }
        return ss.str();
    }

    std::string format_string(const std::string& value)
    {
        std::string s;
        s.push_back('"');
        std::string::size_type n = value.size();
        for (std::string::size_type p = 0; p < n; p++)
        {
            char c = value[p];
            unsigned char uc = c;
            if (c == '\\' || c == '"') {
                s.push_back('\\');
                s.push_back(c);
            }
            else if (c == '\n')
            {
                s.append("\\n");
            }
            else if (uc < 0x20 || uc == 0x7f)
            {
                s.append(format_escaped_unicode(uc));
            }
            else if (uc >= 0xc0 && uc < 0xe0 && n - p >= 2)
            {
                unsigned int codepoint = ((c & 0x1f) << 6)
                    | (value[p+1] & 0x3f);
                s.append(format_escaped_unicode(codepoint));
                p += 1;
            }
            else if (uc >= 0xe0 && uc < 0xf0 && n - p >= 3)
            {
                unsigned int codepoint = ((c & 0x0f) << 12)
                    | ((value[p+1] & 0x3f) << 6)
                    | (value[p+2] & 0x3f);
                s.append(format_escaped_unicode(codepoint));
                p += 2;
            }
            else if (uc >= 0xf0 && uc < 0xf8 && n - p >= 4)
            {
                unsigned int codepoint = ((c & 0x07) << 18)
                    | ((value[p+1] & 0x3f) << 12)
                    | ((value[p+2] & 0x3f) << 6)
                    | (value[p+3] & 0x3f);
                s.append(format_escaped_unicode(codepoint));
                p += 3;
            }
            else
            {
                s.push_back(c);
            }
        }
        s.push_back('"');
        return s;
    }

    void write_value(const std::string& type, const std::string& value)
    {
        os_ << "{\"type\":\"";
        os_ << type;
        os_ << "\",\"value\":";
        os_ << format_string(value);
        os_ << '}';
    }

    std::ostream& os_;
};


int main()
{
    std::string bufstr(
        std::istreambuf_iterator<char>(std::cin),
        std::istreambuf_iterator<char>());

    toml::value toml_data;

    try
    {
        std::istringstream ss(bufstr);
        toml_data = toml::parse(ss);
    }
    catch (const toml::syntax_error& err)
    {
        std::cout << "what(): " << err.what() << std::endl;
        return 1;
    }

    tagged_json_serializer serializer(std::cout);
    toml::visit(serializer, toml_data);
    std::cout << std::endl;

    return 0;
}

